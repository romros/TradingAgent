#!/usr/bin/env python3
"""Frozen low-turnover EUR/USD policy-differential screen."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


def read_fred(path: Path, column: str) -> dict[date, float]:
    result = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = row.get(column, ".")
            if value not in (None, "", "."):
                result[date.fromisoformat(row["observation_date"])] = float(value)
    return result


def friday(day: date) -> date:
    return day + timedelta(days=4 - day.weekday())


def weekly_last(series: dict[date, float]) -> dict[date, float]:
    selected: dict[date, tuple[date, float]] = {}
    for day, value in series.items():
        key = friday(day)
        if key not in selected or day > selected[key][0]:
            selected[key] = (day, value)
    return {key: pair[1] for key, pair in selected.items()}


def build_episodes(price: dict[date, float], ecb: dict[date, float], fed: dict[date, float], lookback: int = 13, threshold: float = 0.25) -> list[dict]:
    weeks = sorted(set(price) & set(ecb) & set(fed))
    executable_states: list[tuple[date, int]] = []
    for index in range(lookback, len(weeks) - 1):
        factor_week, prior, executable_week = weeks[index], weeks[index - lookback], weeks[index + 1]
        change = ((ecb[factor_week] - fed[factor_week]) - (ecb[prior] - fed[prior]))
        state = 1 if change >= threshold else -1 if change <= -threshold else 0
        executable_states.append((executable_week, state))

    episodes = []
    active_state = 0
    entry = None
    for week, state in executable_states:
        if state == active_state:
            continue
        if active_state and entry is not None:
            episodes.append({
                "entry": entry,
                "exit": week,
                "signal": active_state,
                "gross_return": active_state * (price[week] / price[entry] - 1),
            })
        active_state = state
        entry = week if state else None
    return episodes


def summarize(episodes: list[dict], execution_bps: float = 12, annual_financing_pct: float = 8) -> dict:
    yearly = defaultdict(float)
    gains = losses = total = 0.0
    for episode in episodes:
        days = (episode["exit"] - episode["entry"]).days
        cost = execution_bps / 10_000 + annual_financing_pct / 100 * days / 365
        net = episode["gross_return"] - cost
        total += net
        yearly[episode["exit"].year] += net
        if net > 0:
            gains += net
        elif net < 0:
            losses -= net
    positive_years = sum(value > 0 for value in yearly.values())
    return {
        "closed_episodes": len(episodes),
        "long_episodes": sum(row["signal"] == 1 for row in episodes),
        "short_episodes": sum(row["signal"] == -1 for row in episodes),
        "gross_return_sum_pct": round(100 * sum(row["gross_return"] for row in episodes), 6),
        "net_return_sum_pct": round(100 * total, 6),
        "profit_factor_after_stress": round(gains / losses, 6) if losses else math.inf,
        "positive_years": positive_years,
        "years": len(yearly),
        "positive_year_share": round(positive_years / len(yearly), 6) if yearly else 0,
        "yearly_net_pct": {str(year): round(100 * value, 6) for year, value in sorted(yearly.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--price", required=True, type=Path)
    parser.add_argument("--ecb", required=True, type=Path)
    parser.add_argument("--fed", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    episodes = build_episodes(
        weekly_last(read_fred(args.price, "DEXUSEU")),
        weekly_last(read_fred(args.ecb, "ECBDFR")),
        weekly_last(read_fred(args.fed, "DFF")),
    )
    train = [row for row in episodes if date(2006, 1, 1) <= row["entry"] and row["exit"] <= date(2018, 12, 31)]
    metrics = summarize(train)
    passed = metrics["closed_episodes"] >= 30 and metrics["profit_factor_after_stress"] >= 1.2 and metrics["positive_year_share"] >= 0.6 and metrics["net_return_sum_pct"] > 0
    result = {
        "experiment": "eurusd-weekly-policy-differential-v31",
        "split": "TRAIN_ONLY",
        "publication_lag_weeks": 1,
        "sealed_ostium_holdout_accessed": False,
        "proxy_rows_outside_train_ignored": True,
        "metrics": metrics,
        "decision": "OPEN_FROZEN_VALIDATION" if passed else "REJECT_BEFORE_SQ",
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
