#!/usr/bin/env python3
"""Frozen monthly volatility-managed SPY screen with 2024 gated OOS."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "spy_volatility_managed_preregistration_v1.json"
LOCK = HERE / "spy_volatility_managed_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_spec() -> dict:
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if (spec["status"] != "FROZEN_BEFORE_PERFORMANCE"
            or sha(SPEC) != lock["preregistration_sha256"]
            or lock["oos_2024_accessed"] is not False):
        raise ValueError("preregistration lock mismatch")
    return spec


def load_prices(path: Path, allow_oos: bool) -> list[dict]:
    if "2025" in path.name:
        raise ValueError("2025 filename refused")
    result = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.reader(handle):
            if not raw or raw[0].lower() == "date":
                continue
            day = raw[0].replace(".", "-")
            if day > ("2024-12-31" if allow_oos else "2023-12-31"):
                continue
            offset = 2 if len(raw) >= 7 and ":" in raw[1] else 1
            result.append({"date": day, "open": float(raw[offset]),
                           "close": float(raw[offset + 3])})
    return sorted(result, key=lambda row: row["date"])


def daily_returns(rows: list[dict], spec: dict) -> list[dict]:
    rule = spec["rule"]
    lookback = rule["realized_volatility_sessions"]
    weight = 0.0
    result = []
    closes = [row["close"] for row in rows]
    for index in range(lookback + 1, len(rows)):
        row, prior = rows[index], rows[index - 1]
        old_weight = weight
        rebalance = row["date"][:7] != prior["date"][:7]
        if rebalance:
            returns = [closes[j] / closes[j - 1] - 1
                       for j in range(index - lookback, index)]
            realized = statistics.stdev(returns) * math.sqrt(rule["annualization_sessions"])
            weight = min(rule["maximum_weight"], max(rule["minimum_weight"],
                         rule["target_annual_volatility"] / realized)) if realized else rule["maximum_weight"]
        gap = row["open"] / prior["close"] - 1
        intraday = row["close"] / row["open"] - 1
        gross = (1 + old_weight * gap) * (1 + weight * intraday) - 1
        cost = abs(weight - old_weight) * rule["one_way_turnover_cost_bps"] / 10_000
        result.append({"date": row["date"], "return": gross - cost,
                       "benchmark_return": row["close"] / prior["close"] - 1,
                       "weight": weight, "turnover": abs(weight - old_weight)})
    return result


def metrics(rows: list[dict], key: str) -> dict:
    equity = peak = 1.0
    maximum_drawdown = turnover = 0.0
    years: dict[str, float] = {}
    values = []
    for row in rows:
        value = row[key]
        values.append(value)
        equity *= 1 + value
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, 1 - equity / peak)
        years[row["date"][:4]] = years.get(row["date"][:4], 1.0) * (1 + value)
        turnover += row["turnover"] if key == "return" else 0
    mean = statistics.mean(values) if values else 0.0
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"sessions": len(rows), "net_return": equity - 1,
            "annualized_sharpe": mean / std * math.sqrt(252) if std else None,
            "maximum_drawdown": maximum_drawdown, "total_turnover": turnover,
            "average_exposure": statistics.mean(row["weight"] for row in rows) if rows else None,
            "calendar_year_returns": {year: value - 1 for year, value in sorted(years.items())},
            "positive_calendar_years": sum(value > 1 for value in years.values())}


def period(rows: list[dict], bounds: list[str]) -> dict:
    selected = [row for row in rows if bounds[0] <= row["date"] <= bounds[1]]
    strategy, benchmark = metrics(selected, "return"), metrics(selected, "benchmark_return")
    strategy["sharpe_improvement"] = strategy["annualized_sharpe"] - benchmark["annualized_sharpe"]
    strategy["drawdown_ratio_to_buy_and_hold"] = strategy["maximum_drawdown"] / benchmark["maximum_drawdown"]
    return {"strategy": strategy, "buy_and_hold": benchmark}


def passes(value: dict, gate: dict) -> bool:
    strategy = value["strategy"]
    return bool(strategy["sessions"] >= gate["minimum_sessions"]
                and strategy["net_return"] > gate["minimum_net_return"]
                and strategy["sharpe_improvement"] >= gate["minimum_sharpe_improvement"]
                and strategy["drawdown_ratio_to_buy_and_hold"] <= gate["maximum_drawdown_ratio_to_buy_and_hold"]
                and strategy["positive_calendar_years"] >= gate["positive_calendar_years_required"])


def screen(source: Path) -> dict:
    spec = load_spec()
    pre = daily_returns(load_prices(source, False), spec)
    train = period(pre, spec["periods"]["train"])
    validation = period(pre, spec["periods"]["validation"])
    passed = passes(validation, spec["validation_gate"])
    result = {"schema_version": 1, "campaign_id": spec["campaign_id"],
              "preregistration_sha256": sha(SPEC), "source_sha256": sha(source),
              "train": train, "validation": validation,
              "validation_gate_passed": passed,
              "decision": "PASS_VALIDATION_OPEN_OOS" if passed else "REJECT_VALIDATION",
              "oos_2024_accessed": False, "holdout_2025_accessed": False,
              "optimized": False, "paper_authorized": False, "live_authorized": False}
    if passed:
        complete = daily_returns(load_prices(source, True), spec)
        result["oos"] = period(complete, spec["periods"]["oos"])
        result["oos_2024_accessed"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = screen(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
