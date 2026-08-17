#!/usr/bin/env python3
"""Audit non-overlapping SQ long/short equity orders with whole-share economics."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from lab.sq_bridge.ibkr_equity_small_account_audit_v2 import _commission, _number

SHORT_BORROW_RATE = 0.03


def load_orders(path: Path, allow_same_bar_d1: bool = False) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    result = []
    for row in rows:
        if row["Type"] not in {"Buy", "Sell"}:
            raise ValueError("unsupported order side")
        result.append({
            "side": "long" if row["Type"] == "Buy" else "short",
            "open_time": datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S"),
            "close_time": datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S"),
            "open_price": _number(row["Open price"]),
            "close_price": _number(row["Close price"]),
            "sq_size": _number(row["Size"]),
            "sq_pnl": _number(row["Profit/Loss"]),
            "close_type": row.get("Close type"),
            "mae": _number(row["MAE ($)"]) if row.get("MAE ($)") else None,
            "mfe": _number(row["MFE ($)"]) if row.get("MFE ($)") else None,
        })
    result.sort(key=lambda row: row["open_time"])
    if any(row["close_time"] < row["open_time"] for row in result):
        raise ValueError("negative trade duration")
    if any(row["close_time"] == row["open_time"] for row in result) and not allow_same_bar_d1:
        raise ValueError("same-bar D1 trade requires explicit authorization")
    if any(right["open_time"] < left["close_time"] for left, right in zip(result, result[1:])):
        raise ValueError("overlapping positions unsupported")
    for row in result:
        direction = 1 if row["side"] == "long" else -1
        expected = row["sq_size"] * direction * (row["close_price"] - row["open_price"])
        if abs(expected - row["sq_pnl"]) > 0.011:
            raise ValueError("SQ order side/PnL parity mismatch")
    return result


def simulate(orders: list[dict], capital: float, plan: str) -> dict:
    equity = capital
    peak = capital
    drawdown = 0.0
    pnls = []
    quarter = defaultdict(float)
    borrow_total = 0.0
    side_counts = defaultdict(int)
    for order in orders:
        stress = 0.001 if plan == "stress" else 0.0
        direction = 1 if order["side"] == "long" else -1
        entry = order["open_price"] * (1 + direction * stress)
        exit_price = order["close_price"] * (1 - direction * stress)
        shares = math.floor(equity / entry)
        if shares < 1:
            raise ValueError("capital cannot support one whole share")
        days = (order["close_time"] - order["open_time"]).total_seconds() / 86400
        borrow = (shares * entry * SHORT_BORROW_RATE * days / 365.2425
                  if order["side"] == "short" else 0.0)
        net = shares * direction * (exit_price - entry) \
            - _commission(plan, shares) * 2 - borrow
        equity += net
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak)
        key = f"{order['open_time'].year}-Q{(order['open_time'].month - 1) // 3 + 1}"
        quarter[key] += net
        pnls.append(net)
        borrow_total += borrow
        side_counts[order["side"]] += 1
    gains = sum(max(value, 0) for value in pnls)
    losses = sum(max(-value, 0) for value in pnls)
    return {
        "plan": plan, "initial_capital_usd": capital,
        "final_equity_usd": round(equity, 6),
        "return_pct": round((equity / capital - 1) * 100, 6),
        "trades": len(pnls), "long_trades": side_counts["long"],
        "short_trades": side_counts["short"],
        "profit_factor": round(gains / losses, 6) if losses else None,
        "maximum_drawdown_pct_close_to_close": round(drawdown * 100, 6),
        "short_borrow_cost_usd": round(borrow_total, 6),
        "positive_quarters": sum(value > 0 for value in quarter.values()),
        "quarters": len(quarter),
        "quarter_pnl_usd": {key: round(value, 6) for key, value in sorted(quarter.items())},
    }


def audit(candidate: str, orders_path: Path, capital: float = 1000) -> dict:
    orders = load_orders(orders_path, allow_same_bar_d1=True)
    return {
        "schema_version": 1, "stage": "VALIDATION_2022_2023",
        "candidate_id": candidate, "orders_csv_path": str(orders_path.resolve()),
        "orders_csv_sha256": hashlib.sha256(orders_path.read_bytes()).hexdigest(),
        "sizing": "whole_shares_one_times_equity_no_portfolio_overlap",
        "short_borrow_rate_annual": SHORT_BORROW_RATE,
        "cost_contract": "tiered/fixed; stress=fixed plus 10bps each side; short borrow 3% annual",
        "results": {plan: simulate(orders, capital, plan)
                    for plan in ("tiered", "fixed", "stress")},
        "oos_2024_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--capital", type=float, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.candidate_id, args.orders, args.capital)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["results"], indent=2))


if __name__ == "__main__":
    main()
