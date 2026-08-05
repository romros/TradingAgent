#!/usr/bin/env python3
"""Simula una cartera event-driven amb risc, marge, costos i compounding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def simulate(case: dict) -> dict:
    equity = float(case["initial_equity"])
    peak = equity
    max_drawdown = 0.0
    open_positions: dict[str, dict] = {}
    accepted, skipped, ledger = 0, 0, []
    events = []
    for trade in case["trades"]:
        events.append((trade["entry_time"], 1, trade["asset"], "entry", trade))
        events.append((trade["exit_time"], 0, trade["asset"], "exit", trade))
    for timestamp, _, asset, kind, trade in sorted(events):
        key = f"{asset}:{trade['entry_time']}:{trade['exit_time']}"
        if kind == "exit":
            position = open_positions.pop(key, None)
            if position is None:
                continue
            gross = position["notional"] * float(trade["return_on_notional"])
            rollover = position["notional"] * float(trade.get("rollover_bps", 0)) / 10000
            net = gross - rollover
            equity += net
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 1)
            ledger.append({"time": timestamp, "asset": asset, "event": "exit", "net_pnl": round(net, 8), "equity": round(equity, 8)})
            continue

        stop_distance = float(trade["stop_distance_pct"]) / 100
        risk_amount = equity * float(trade["risk_pct"]) / 100
        notional = risk_amount / stop_distance if stop_distance > 0 else float("inf")
        leverage = float(trade["leverage"])
        collateral = notional / leverage if leverage > 0 else float("inf")
        used_collateral = sum(item["collateral"] for item in open_positions.values())
        open_notional = sum(item["notional"] for item in open_positions.values())
        opening_fee = notional * float(trade["opening_fee_bps"]) / 10000
        oracle_fee = float(trade.get("oracle_fee", case.get("oracle_fee", 0.1)))
        projected_equity = equity - opening_fee - oracle_fee
        reasons = []
        if leverage > float(trade.get("pair_max_leverage", leverage)):
            reasons.append("pair_leverage_cap")
        if used_collateral + collateral > projected_equity:
            reasons.append("free_margin")
        if projected_equity > 0 and (open_notional + notional) / projected_equity > float(case["maximum_effective_leverage"]):
            reasons.append("portfolio_leverage_cap")
        if sum(item["risk_amount"] for item in open_positions.values()) + risk_amount > equity * float(case["maximum_simultaneous_risk_pct"]) / 100:
            reasons.append("simultaneous_risk_cap")
        if reasons:
            skipped += 1
            ledger.append({"time": timestamp, "asset": asset, "event": "skipped", "reasons": reasons, "equity": round(equity, 8)})
            continue
        equity = projected_equity
        accepted += 1
        open_positions[key] = {"notional": notional, "collateral": collateral, "risk_amount": risk_amount}
        ledger.append({"time": timestamp, "asset": asset, "event": "entry", "notional": round(notional, 8), "collateral": round(collateral, 8), "equity": round(equity, 8)})

    return {
        "initial_equity": case["initial_equity"],
        "final_equity": round(equity, 8),
        "net_return_pct": round((equity / case["initial_equity"] - 1) * 100, 8),
        "maximum_drawdown_pct": round(max_drawdown * 100, 8),
        "accepted_trades": accepted,
        "skipped_trades": skipped,
        "open_positions_at_end": len(open_positions),
        "ledger": ledger,
        "limits": "Simulació de recerca; no modela liquidació intrabar sense una trajectòria de preus explícita.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    print(json.dumps(simulate(json.loads(args.case.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
