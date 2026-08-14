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
LIQUIDATION_MARGIN_PCT = 25.0


def price_for(side: str, opening: bool, quote: dict) -> float:
    simulated = quote.get("simulated_slippage_250")
    if simulated:
        execution_side = "long" if (side == "B") == opening else "short"
        points = simulated.get(execution_side) or []
        point = next((row for row in points if float(row.get("ntl", 0)) == 250.0), None)
        if point:
            impact_fraction = float(point["slippage"]) / 100
            mid = float(quote["mid"])
            return mid * (1 + impact_fraction if execution_side == "long"
                          else 1 - impact_fraction)
    key = "ask" if (side == "B") == opening else "bid"
    return float(quote[key])


def liquidation_price(entry: float, side: str, collateral: float, leverage: float,
                      venue_max_leverage: float, accrued_cost: float = 0.0) -> float:
    margin_fraction = LIQUIDATION_MARGIN_PCT / 100 * leverage / venue_max_leverage
    distance = max(0.0, 1 - margin_fraction - accrued_cost / collateral) / leverage
    return entry * (1 - distance if side == "B" else 1 + distance)


def carry_cost(position: dict, exit_quote: dict, exited_at: str, notional: float) -> float | None:
    entry_rates = position.get("entry_rollover_rate") or {}
    exit_rates = exit_quote.get("rollover_rate") or {}
    rate_key = "long" if position["side"] == "B" else "short"
    if rate_key not in entry_rates or rate_key not in exit_rates:
        return None
    entry_time = datetime.fromisoformat(position["entry_detected_at"].replace("Z", "+00:00"))
    exit_time = datetime.fromisoformat(exited_at.replace("Z", "+00:00"))
    periods = max(0.0, (exit_time - entry_time).total_seconds() / (8 * 3600))
    # SDK display is negative when the trader pays. Never infer future credits.
    rate_pct = max(0.0, -float(entry_rates[rate_key]), -float(exit_rates[rate_key]))
    return notional * rate_pct / 100 * periods


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
            minimum_notional = float(quote.get("min_notional_usd") or 0)
            venue_max_leverage = float(quote.get("max_leverage") or 0)
            if minimum_notional <= 0 or venue_max_leverage <= 0:
                contract_complete = False
            else:
                contract_complete = notional >= minimum_notional and leverage <= venue_max_leverage
            if minimum_notional > 0 and notional < minimum_notional:
                skipped.append({"position_sha256": key, "action": action,
                                "reason": "paper_notional_below_contract_minimum"})
                continue
            entry = price_for(row.get("side"), True, quote)
            open_fee = notional * float(quote.get("open_fee_bps") or 0) / 10_000
            positions[key] = {"wallet_sha256": row.get("wallet_sha256"), "pair": row.get("pair"),
                              "position_sha256": key,
                              "side": row.get("side"), "entry_price": entry,
                              "source_entry_price": float(row.get("execution_price") or 0),
                              "entry_detected_at": row.get("detected_at"),
                              "entry_executed_at": row.get("executed_at"),
                              "entry_detection_latency_seconds": row.get("detection_latency_seconds"),
                              "source_notional_remaining": source_notional,
                              "paper_notional_remaining": notional,
                              "collateral_usdc": collateral, "leverage": leverage,
                              "open_fee_remaining": open_fee,
                              "minimum_notional_usdc": minimum_notional or None,
                              "venue_max_leverage": venue_max_leverage or None,
                              "contract_limits_complete": contract_complete,
                              "entry_rollover_rate": quote.get("rollover_rate")}
            positions[key]["liquidation_price_initial"] = (
                liquidation_price(entry, row.get("side"), collateral, leverage,
                                  venue_max_leverage) if contract_complete else None)
            positions[key]["slippage_model"] = (
                "sdk_simulated_250" if quote.get("simulated_slippage_250") else "bid_ask_fallback")
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
        source_entry = position["source_entry_price"]
        source_exit = float(row.get("execution_price") or 0)
        source_return = (direction * (source_exit / source_entry - 1.0)
                         if source_entry > 0 and source_exit > 0 else None)
        copy_gross_return = direction * (exit_price / entry - 1.0)
        return_retention = (copy_gross_return / source_return
                            if source_return not in (None, 0.0) and source_return > 0 else None)
        implementation_shortfall = (None if source_return is None
                                    else (source_return - copy_gross_return) * 10_000)
        open_fee = position["open_fee_remaining"] * fraction
        close_fee = paper_notional * float(quote.get("close_fee_bps") or 0) / 10_000
        carry = carry_cost(position, quote, row["detected_at"], paper_notional)
        execution_complete = (position["slippage_model"] == "sdk_simulated_250"
                              and bool(quote.get("simulated_slippage_250")))
        cost_complete = (carry is not None and execution_complete
                         and position.get("contract_limits_complete") is True)
        net = gross - open_fee - close_fee - carry if cost_complete else None
        if net is not None:
            equity += net
        closed.append({"wallet_sha256": position["wallet_sha256"], "position_sha256": key,
                       "pair": position["pair"], "action": action,
                       "entry_observed_price": entry, "exit_observed_price": exit_price,
                       "entry_slippage_model": position["slippage_model"],
                       "exit_slippage_model": (
                           "sdk_simulated_250" if quote.get("simulated_slippage_250")
                           else "bid_ask_fallback"),
                       "source_entry_price": source_entry, "source_exit_price": source_exit,
                       "paper_notional_usdc": paper_notional, "gross_pnl_usdc": gross,
                       "open_fee_usdc": open_fee, "close_fee_usdc": close_fee,
                       "carry_cost_usdc": carry,
                       "copy_net_pnl_usdc": net, "cost_complete": cost_complete,
                       "source_gross_return_pct": None if source_return is None else 100 * source_return,
                       "copy_gross_return_pct": 100 * copy_gross_return,
                       "implementation_shortfall_bps": implementation_shortfall,
                       "profitable_source_return_retained_pct": (
                           None if return_retention is None else 100 * return_retention),
                       "liquidation_price_initial": position.get("liquidation_price_initial"),
                       "cost_note": ("conservative observed rollover, SDK size slippage and contract limits"
                                     if cost_complete else "execution or contract evidence incomplete"),
                       "entry_detection_latency_seconds": position["entry_detection_latency_seconds"],
                       "exit_detection_latency_seconds": row.get("detection_latency_seconds")})
        position["source_notional_remaining"] -= source_close
        position["paper_notional_remaining"] -= paper_notional
        position["open_fee_remaining"] -= open_fee
        if position["source_notional_remaining"] <= 1e-9 or fraction >= 1.0:
            del positions[key]
    realism_eligible = [row for row in closed if row["cost_complete"]]
    blockers = []
    if not realism_eligible:
        blockers.append("no realism-eligible prospectively copied closed trades")
    if any(row.get("reason") == "position_increase_not_supported_v1" for row in skipped):
        blockers.append("position increases are not simulated")
    return {"schema_version": 1, "mode": "SHADOW_PAPER_NO_ORDERS",
            "execution_realism_pass": not blockers,
            "execution_realism_blockers": blockers,
            "execution_realism_eligible_closed": len(realism_eligible),
            "execution_realism_excluded_closed": len(closed) - len(realism_eligible),
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
