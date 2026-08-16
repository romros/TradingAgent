#!/usr/bin/env python3
"""Frozen whole-share and IBKR-cost gate for recent Connors RSI(2)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date
from pathlib import Path

from connors_rsi2_recent_confirmation_screen_v1 import load, subset
from connors_rsi2_screen_v1 import trades

HERE = Path(__file__).resolve().parent
SPEC = HERE / "connors_rsi2_small_account_preregistration_v1.json"
LOCK = HERE / "connors_rsi2_small_account_preregistration_v1.lock.json"
ROOT = HERE.parents[1]
START = date(2025, 1, 1)
END = date(2026, 5, 29)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pnl_metrics(items: list[dict], capital: float) -> dict:
    values = [item["net_pnl"] for item in sorted(items, key=lambda item: item["exit"])]
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    equity = peak = capital
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
    return {
        "trades": len(values),
        "wins": sum(value > 0 for value in values),
        "net_pnl_usd": round(sum(values), 6),
        "net_return_pct_on_total_capital": round(sum(values) / capital * 100, 6),
        "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else None,
        "closed_trade_max_drawdown_pct": round(max_drawdown, 6),
    }


def screen(paths: dict[str, Path]) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]:
        raise ValueError("preregistration lock mismatch")
    upstream = ROOT / spec["upstream_result"]
    if sha(upstream) != spec["upstream_result_sha256"]:
        raise ValueError("upstream result hash mismatch")
    if set(paths) != {"AAPL", "JPM", "SPY"}:
        raise ValueError("frozen universe required")
    capital = float(spec["capital_usd"])
    sleeve = capital / len(paths)
    raw = {}
    for asset, path in paths.items():
        rows = load(path, END)
        opens = {row[0]: row[1] for row in rows}
        raw[asset] = []
        for trade in subset(trades(rows), START, END):
            entry_price, exit_price = opens[trade["entry"]], opens[trade["exit"]]
            size = math.floor(sleeve / entry_price)
            if size:
                raw[asset].append({**trade, "entry_price": entry_price, "exit_price": exit_price, "shares": size})
    scenarios = {}
    for name, costs in spec["cost_scenarios"].items():
        by_asset = {}
        combined = []
        for asset, items in raw.items():
            net_items = []
            for item in items:
                friction = 2 * costs["minimum_per_order_usd"] + item["shares"] * (item["entry_price"] + item["exit_price"]) * costs["bps_per_side"] / 10000
                net_items.append({**item, "net_pnl": item["shares"] * (item["exit_price"] - item["entry_price"]) - friction})
            combined.extend(net_items)
            by_asset[asset] = pnl_metrics(net_items, sleeve)
        scenarios[name] = {
            "combined": pnl_metrics(combined, capital),
            "year_2025": pnl_metrics([item for item in combined if item["entry"].year == 2025 and item["exit"].year == 2025], capital),
            "by_asset": by_asset,
            "positive_assets": sum(value["net_pnl_usd"] > 0 for value in by_asset.values()),
        }
    stress = scenarios["stress"]
    gate = spec["frozen_gate"]
    result = stress["combined"]
    passed = (
        result["net_pnl_usd"] > gate["stress_net_pnl_strictly_above_usd"]
        and (result["profit_factor"] or 0) >= gate["stress_profit_factor_at_least"]
        and stress["year_2025"]["net_pnl_usd"] > gate["stress_year_2025_net_pnl_strictly_above_usd"]
        and stress["positive_assets"] >= gate["stress_minimum_positive_assets"]
        and result["closed_trade_max_drawdown_pct"] <= gate["stress_closed_trade_drawdown_at_most_pct"]
        and result["trades"] >= gate["minimum_executed_trades"]
    )
    return {
        "schema_version": 1,
        "decision": "PASS_SMALL_ACCOUNT_COST_GATE" if passed else "REJECT_SMALL_ACCOUNT_COST_GATE",
        "preregistration_sha256": sha(SPEC),
        "capital_usd": capital,
        "fixed_sleeve_usd": sleeve,
        "scenarios": scenarios,
        "sq_translation_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {name: Path(path) for name, path in (item.split("=", 1) for item in args.asset)}
    result = screen(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
