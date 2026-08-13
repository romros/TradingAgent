#!/usr/bin/env python3
"""Replay observable Wolfpack fills as a finite, non-trading shadow portfolio."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

CLOSES = {"Close", "StopLoss", "TakeProfit", "Liquidation", "CloseDayTrade"}
STARTING_EQUITY = 500.0
MAX_POSITION_COLLATERAL = 50.0
MAX_TOTAL_COLLATERAL = 300.0
MAX_LEVERAGE = 5.0


def price_for(side: str, opening: bool, quote: dict) -> float:
    key = "ask" if (side == "B") == opening else "bid"
    return float(quote[key])


def replay(rows: list[dict]) -> dict:
    positions: dict[str, dict] = {}
    closed, skipped = [], []
    equity = STARTING_EQUITY
    for row in rows:
        key = row.get("position_sha256")
        quote = row.get("observed_quote")
        if not key or not quote or quote.get("bid") is None or quote.get("ask") is None:
            skipped.append({"position_sha256": key, "action": row.get("action"),
                            "reason": "missing_observable_bid_ask"})
            continue
        if not quote.get("market_open", False):
            skipped.append({"position_sha256": key, "action": row.get("action"),
                            "reason": "market_closed_at_detection"})
            continue
        action = row.get("action")
        if action == "Open":
            if key in positions:
                skipped.append({"position_sha256": key, "action": action,
                                "reason": "position_increase_not_supported_v1"})
                continue
            used = sum(position["collateral_usdc"] for position in positions.values())
            available = max(0.0, MAX_TOTAL_COLLATERAL - used)
            source_collateral = float(row.get("collateral_usd") or 0)
            source_notional = float(row.get("notional_usd") or 0)
            source_leverage = source_notional / source_collateral if source_collateral > 0 else 0
            collateral = min(MAX_POSITION_COLLATERAL, available)
            leverage = min(source_leverage, MAX_LEVERAGE)
            if collateral <= 0 or leverage <= 0:
                skipped.append({"position_sha256": key, "action": action,
                                "reason": "paper_risk_capacity_or_leverage_unavailable"})
                continue
            notional = collateral * leverage
            entry = price_for(row.get("side"), True, quote)
            open_fee = notional * float(quote.get("open_fee_bps") or 0) / 10_000
            positions[key] = {"wallet_sha256": row.get("wallet_sha256"), "pair": row.get("pair"),
                              "side": row.get("side"), "entry_price": entry,
                              "entry_detected_at": row.get("detected_at"),
                              "source_notional_remaining": source_notional,
                              "paper_notional_remaining": notional,
                              "collateral_usdc": collateral, "leverage": leverage,
                              "open_fee_remaining": open_fee}
            continue
        if action not in CLOSES:
            continue
        position = positions.get(key)
        if not position:
            skipped.append({"position_sha256": key, "action": action,
                            "reason": "open_not_observed_prospectively"})
            continue
        source_close = float(row.get("notional_usd") or 0)
        source_remaining = position["source_notional_remaining"]
        fraction = min(1.0, source_close / source_remaining) if source_remaining > 0 else 1.0
        paper_notional = position["paper_notional_remaining"] * fraction
        entry = position["entry_price"]
        exit_price = price_for(position["side"], False, quote)
        direction = 1.0 if position["side"] == "B" else -1.0
        gross = paper_notional * direction * (exit_price / entry - 1.0)
        open_fee = position["open_fee_remaining"] * fraction
        close_fee = paper_notional * float(quote.get("close_fee_bps") or 0) / 10_000
        entry_day = datetime.fromisoformat(position["entry_detected_at"].replace("Z", "+00:00")).date()
        exit_day = datetime.fromisoformat(row["detected_at"].replace("Z", "+00:00")).date()
        cost_complete = entry_day == exit_day
        net = gross - open_fee - close_fee if cost_complete else None
        if net is not None:
            equity += net
        closed.append({"wallet_sha256": position["wallet_sha256"], "position_sha256": key,
                       "pair": position["pair"], "action": action,
                       "entry_observed_price": entry, "exit_observed_price": exit_price,
                       "paper_notional_usdc": paper_notional, "gross_pnl_usdc": gross,
                       "open_fee_usdc": open_fee, "close_fee_usdc": close_fee,
                       "carry_cost_usdc": 0.0 if cost_complete else None,
                       "copy_net_pnl_usdc": net, "cost_complete": cost_complete,
                       "cost_note": "same UTC day; no daily rollover boundary modelled" if cost_complete
                                    else "cross-day rollover contract not reconciled",
                       "detection_latency_seconds": row.get("detection_latency_seconds")})
        position["source_notional_remaining"] -= source_close
        position["paper_notional_remaining"] -= paper_notional
        position["open_fee_remaining"] -= open_fee
        if position["source_notional_remaining"] <= 1e-9 or fraction >= 1.0:
            del positions[key]
    return {"schema_version": 1, "mode": "SHADOW_PAPER_NO_ORDERS",
            "execution_realism_pass": False,
            "execution_realism_blockers": [
                "size-dependent simulated slippage not captured per event",
                "cross-day rollover and funding not reconciled",
                "position increases are not simulated",
                "liquidation and contract minimums are not modelled",
            ],
            "starting_equity_usdc": STARTING_EQUITY, "ending_equity_usdc": equity,
            "closed": closed, "open_positions": list(positions.values()), "skipped": skipped,
            "limits": {"max_position_collateral_usdc": MAX_POSITION_COLLATERAL,
                       "max_total_collateral_usdc": MAX_TOTAL_COLLATERAL,
                       "max_leverage": MAX_LEVERAGE}, "live_trading_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follows", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration-hours", type=float, default=0.0)
    parser.add_argument("--interval-seconds", type=int, default=900)
    args = parser.parse_args()
    if not 0 <= args.duration_hours <= 1440:
        raise SystemExit("--duration-hours must be 0..1440")
    if not 30 <= args.interval_seconds <= 86400:
        raise SystemExit("--interval-seconds must be 30..86400")
    deadline = time.time() + args.duration_hours * 3600
    while True:
        rows = [json.loads(line) for line in args.follows.read_text().splitlines() if line.strip()]
        # Dedicated name avoids colliding with a host-side preview in a sticky /tmp.
        temporary = args.output.with_suffix(args.output.suffix + ".container-next")
        temporary.write_text(json.dumps(replay(rows), indent=2, ensure_ascii=False) + "\n")
        temporary.replace(args.output)
        if args.duration_hours == 0 or time.time() >= deadline:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
