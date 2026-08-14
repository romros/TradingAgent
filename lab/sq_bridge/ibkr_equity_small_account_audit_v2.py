#!/usr/bin/env python3
"""Audit an SQ US-equity orders CSV with executable whole-share IBKR sizing."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _commission(plan: str, shares: int) -> float:
    if plan == "tiered":
        return max(0.35, 0.0035 * shares)
    if plan in {"fixed", "stress"}:
        return max(1.0, 0.005 * shares)
    raise ValueError("unknown commission plan")


def load_orders(path: Path, *, allow_same_bar_d1: bool = False) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    orders = []
    for row in rows:
        if row["Type"] != "Buy":
            raise ValueError("audit currently supports long-only candidates")
        orders.append({
            "open_time": datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S"),
            "close_time": datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S"),
            "open_price": _number(row["Open price"]),
            "close_price": _number(row["Close price"]),
            "sq_size": _number(row["Size"]) if row.get("Size") else 1.0,
            "sq_pnl_one_share": _number(row["Profit/Loss"]),
            "close_type": row.get("Close type"),
            "mae": _number(row["MAE ($)"]) if row.get("MAE ($)") else None,
            "mfe": _number(row["MFE ($)"]) if row.get("MFE ($)") else None,
        })
    orders.sort(key=lambda row: row["open_time"])
    same_bar = [row for row in orders if row["close_time"] == row["open_time"]]
    if any(row["close_time"] < row["open_time"] for row in orders):
        raise ValueError("non-positive trade duration")
    def valid_same_bar(row: dict) -> bool:
        if row["mae"] is None or row["mfe"] is None:
            return False
        if row["close_type"] == "SL":
            return (row["close_price"] < row["open_price"]
                    and abs(row["mae"] - row["sq_pnl_one_share"]) <= .011)
        if row["close_type"] == "PT":
            return (row["close_price"] > row["open_price"]
                    and abs(row["mfe"] - row["sq_pnl_one_share"]) <= .011)
        if row["close_type"] == "EndTest":
            expected = row["sq_size"] * (row["close_price"] - row["open_price"])
            return abs(expected - row["sq_pnl_one_share"]) <= .011
        return False
    if same_bar and (not allow_same_bar_d1 or any(
            not valid_same_bar(row) for row in same_bar)):
        raise ValueError("non-positive trade duration")
    if any(right["open_time"] < left["close_time"]
           for left, right in zip(orders, orders[1:])):
        raise ValueError("overlapping positions require a portfolio cash ledger")
    return orders


def simulate(orders: list[dict], *, initial_capital: float, plan: str) -> dict:
    if not math.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial capital must be positive")
    equity = initial_capital
    peak = equity
    max_drawdown = 0.0
    results = []
    quarter_pnl: dict[str, float] = defaultdict(float)
    for order in orders:
        slippage_bps = 10.0 if plan == "stress" else 0.0
        entry = order["open_price"] * (1 + slippage_bps / 10_000)
        exit_price = order["close_price"] * (1 - slippage_bps / 10_000)
        shares = math.floor(equity / entry)
        if shares < 1:
            raise ValueError("capital cannot buy one whole share")
        entry_fee = _commission(plan, shares)
        exit_fee = _commission(plan, shares)
        net = shares * (exit_price - entry) - entry_fee - exit_fee
        equity += net
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
        quarter = f"{order['open_time'].year}-Q{(order['open_time'].month - 1) // 3 + 1}"
        quarter_pnl[quarter] += net
        results.append({
            **order, "shares": shares, "entry_fee": entry_fee,
            "exit_fee": exit_fee, "net_pnl": net, "equity_after": equity,
            "duration_hours": (order["close_time"] - order["open_time"]).total_seconds() / 3600,
        })
    wins = [row["net_pnl"] for row in results if row["net_pnl"] > 0]
    losses = [-row["net_pnl"] for row in results if row["net_pnl"] < 0]
    pnl = sum(row["net_pnl"] for row in results)
    top_three = sum(sorted((max(0.0, row["net_pnl"]) for row in results), reverse=True)[:3])
    durations = sorted(row["duration_hours"] for row in results)
    return {
        "plan": plan, "initial_capital_usd": initial_capital,
        "final_equity_usd": round(equity, 6), "net_pnl_usd": round(pnl, 6),
        "return_pct": round((equity / initial_capital - 1) * 100, 6),
        "trades": len(results),
        "profit_factor": round(sum(wins) / sum(losses), 6) if losses else None,
        "win_rate": round(len(wins) / len(results), 6) if results else None,
        "net_expectancy_usd": round(pnl / len(results), 6) if results else None,
        "maximum_drawdown_pct_close_to_close": round(max_drawdown * 100, 6),
        "minimum_shares": min(row["shares"] for row in results),
        "maximum_shares": max(row["shares"] for row in results),
        "median_duration_hours": round(durations[len(durations) // 2], 6),
        "maximum_duration_hours": round(max(durations), 6),
        "top_three_winners_share_of_net_profit": (
            round(top_three / pnl, 6) if pnl > 0 else None),
        "positive_quarters": sum(value > 0 for value in quarter_pnl.values()),
        "quarters": len(quarter_pnl),
        "quarter_pnl_usd": {key: round(value, 6) for key, value in sorted(quarter_pnl.items())},
    }


def audit(*, candidate_id: str, orders_path: Path,
          capital_scenarios: list[float], allow_same_bar_d1: bool = False,
          stage: str = "validation") -> dict:
    if stage not in {"validation", "oos", "holdout"}:
        raise ValueError("audit stage must be validation, oos or holdout")
    orders = load_orders(orders_path, allow_same_bar_d1=allow_same_bar_d1)
    return {
        "schema_version": 1,
        "stage": f"IBKR_EQUITY_SMALL_ACCOUNT_{stage.upper()}_AUDIT",
        "candidate_id": candidate_id,
        "orders_csv_path": str(orders_path.resolve()),
        "orders_csv_sha256": _sha(orders_path),
        "sizing": "whole_shares_all_available_realized_equity_no_leverage",
        "same_bar_d1_policy": (
            "allow_verified_SL_MAE_or_PT_MFE_or_exact_EndTest_mark_to_market"
            if allow_same_bar_d1 else "forbidden"),
        "same_bar_d1_trade_count": sum(
            row["open_time"] == row["close_time"] for row in orders),
        "cost_contract": {
            "tiered": "max(USD 0.35, USD 0.0035/share) per order",
            "fixed": "max(USD 1.00, USD 0.005/share) per order",
            "stress": "fixed commission plus 10 bps adverse slippage per side",
        },
        "results": {str(int(capital)): {
            plan: simulate(orders, initial_capital=capital, plan=plan)
            for plan in ("tiered", "fixed", "stress")
        } for capital in capital_scenarios},
        "oos_2024_accessed": stage == "oos",
        "holdout_2025_accessed": stage == "holdout",
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--capital", action="append", type=float, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-same-bar-d1", action="store_true")
    parser.add_argument("--stage", choices=("validation", "oos", "holdout"),
                        default="validation")
    args = parser.parse_args()
    result = audit(candidate_id=args.candidate_id, orders_path=args.orders,
                   capital_scenarios=args.capital,
                   allow_same_bar_d1=args.allow_same_bar_d1, stage=args.stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result["results"], indent=2))


if __name__ == "__main__":
    main()
