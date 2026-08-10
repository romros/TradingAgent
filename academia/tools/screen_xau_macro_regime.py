#!/usr/bin/env python3
"""Frozen cheap screen for the XAU real-yield/dollar regime."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


def read_fred(path: Path, column: str) -> dict[date, float]:
    values = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = row.get(column, ".")
            if raw not in (None, "", "."):
                values[date.fromisoformat(row["observation_date"])] = float(raw)
    return values


def read_lbma(path: Path) -> dict[date, float]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {date.fromisoformat(row["d"]): float(row["v"][0]) for row in rows if row.get("v") and row["v"][0]}


def week_end(day: date) -> date:
    return day + timedelta(days=4 - day.weekday())


def weekly_last(daily: dict[date, float]) -> dict[date, float]:
    result: dict[date, tuple[date, float]] = {}
    for day, value in daily.items():
        key = week_end(day)
        if key not in result or day > result[key][0]:
            result[key] = (day, value)
    return {key: item[1] for key, item in result.items()}


def metrics(trades: list[dict], cost_bps: float) -> dict:
    cost = cost_bps / 10_000
    net = [trade["signed_return"] - cost for trade in trades]
    gains = sum(value for value in net if value > 0)
    losses = -sum(value for value in net if value < 0)
    years: dict[int, float] = defaultdict(float)
    for trade, value in zip(trades, net):
        years[trade["date"].year] += value
    positive_years = sum(value > 0 for value in years.values())
    return {
        "trades": len(trades),
        "long_trades": sum(trade["signal"] == 1 for trade in trades),
        "short_trades": sum(trade["signal"] == -1 for trade in trades),
        "gross_return_sum_pct": round(100 * sum(trade["signed_return"] for trade in trades), 6),
        "net_return_sum_pct": round(100 * sum(net), 6),
        "mean_net_bps": round(10_000 * sum(net) / len(net), 6) if net else None,
        "profit_factor_after_cost": round(gains / losses, 6) if losses else math.inf,
        "positive_years": positive_years,
        "years": len(years),
        "positive_year_share": round(positive_years / len(years), 6) if years else 0,
        "yearly_net_pct": {str(year): round(100 * value, 6) for year, value in sorted(years.items())},
    }


def build_trades(gold: dict[date, float], real_yield: dict[date, float], dollar: dict[date, float], lookback: int) -> list[dict]:
    common = sorted(set(gold) & set(real_yield) & set(dollar))
    trades = []
    for index in range(lookback, len(common) - 2):
        factor_week, prior = common[index], common[index - lookback]
        entry_week, exit_week = common[index + 1], common[index + 2]
        real_change = real_yield[factor_week] - real_yield[prior]
        dollar_return = dollar[factor_week] / dollar[prior] - 1
        signal = 1 if real_change < 0 and dollar_return < 0 else -1 if real_change > 0 and dollar_return > 0 else 0
        if signal:
            trades.append({
                "date": entry_week,
                "factor_date": factor_week,
                "signal": signal,
                "signed_return": signal * (gold[exit_week] / gold[entry_week] - 1),
            })
    return trades


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--real-yield", type=Path, required=True)
    parser.add_argument("--dollar", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    trades = build_trades(
        weekly_last(read_lbma(args.gold)),
        weekly_last(read_fred(args.real_yield, "DFII10")),
        weekly_last(read_fred(args.dollar, "DTWEXBGS")),
        13,
    )
    train = [trade for trade in trades if date(2006, 1, 1) <= trade["date"] <= date(2018, 12, 31)]
    result = {
        "experiment": "xau-weekly-real-yield-dollar-v30",
        "split": "TRAIN_ONLY",
        "sealed_ostium_holdout_accessed": False,
        "proxy_rows_outside_train_ignored": True,
        "publication_lag_weeks": 1,
        "stress_cost_bps": 35,
        "metrics": metrics(train, 35),
    }
    gate = result["metrics"]
    passed = gate["trades"] >= 80 and gate["profit_factor_after_cost"] >= 1.2 and gate["positive_year_share"] >= 0.6 and gate["net_return_sum_pct"] > 0
    result["decision"] = "OPEN_FROZEN_VALIDATION" if passed else "REJECT_BEFORE_SQ"
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
