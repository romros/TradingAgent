#!/usr/bin/env python3
"""Deterministic cost-stress and bootstrap robustness for D1 finalists."""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def gross_rows(candidate: dict) -> list[tuple[str, float]]:
    rows = []
    with Path(candidate["orders_csv_path"]).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            day = datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S").date().isoformat()
            rows.append((day, number(row["Profit/Loss"])))
    return rows


def metrics(values: list[float]) -> dict:
    gp, gl = sum(max(0, x) for x in values), -sum(min(0, x) for x in values)
    equity = peak = dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return {"observations": len(values), "net_profit": round(sum(values), 2),
            "profit_factor": round(gp / gl, 4) if gl else None,
            "expectancy": round(sum(values) / len(values), 2) if values else None,
            "maximum_drawdown": round(dd, 2)}


def bootstrap(values: list[float], runs: int, seed: int) -> dict:
    rng = random.Random(seed)
    profits, drawdowns = [], []
    for _ in range(runs):
        sample = [values[rng.randrange(len(values))] for _ in values]
        measured = metrics(sample)
        profits.append(measured["net_profit"])
        drawdowns.append(measured["maximum_drawdown"])
    profits.sort(); drawdowns.sort()
    return {
        "runs": runs, "seed": seed,
        "profitable_ratio": round(sum(value > 0 for value in profits) / runs, 4),
        "profit_p05": profits[int(0.05 * (runs - 1))],
        "drawdown_p95": drawdowns[int(0.95 * (runs - 1))],
        "drawdown_p99": drawdowns[int(0.99 * (runs - 1))],
    }


def build(temporal_path: Path, portfolio_path: Path, output: Path) -> dict:
    temporal, portfolios = json.loads(temporal_path.read_text()), json.loads(portfolio_path.read_text())
    candidates = {row["case"]: row for row in temporal["results"]}
    finalists = [row["case"] for row in temporal["results"] if row["passes_temporal_gate"]]
    top = (portfolios.get("passing_portfolios") or [])[:1]
    subjects = [(case, [case]) for case in finalists]
    subjects += [(row["portfolio_id"], row["cases"]) for row in top]
    results = []
    for subject_id, cases in subjects:
        source = [item for case in cases for item in gross_rows(candidates[case])]
        by_day = defaultdict(float)
        for day, pnl in source:
            by_day[day] += pnl
        scenarios = {}
        for label, cost in (("base", 2.0), ("conservative", 3.0), ("stress", 4.0)):
            daily_cost = defaultdict(float)
            for day, _ in source:
                daily_cost[day] += cost
            values = [by_day[day] - daily_cost[day] for day in sorted(by_day)]
            scenarios[label] = metrics(values)
        base_values = []
        for day in sorted(by_day):
            trades = sum(1 for trade_day, _ in source if trade_day == day)
            base_values.append(by_day[day] - 2.0 * trades)
        mc = bootstrap(base_values, 2000, 20260812)
        passes = ((scenarios["stress"]["profit_factor"] or 0) >= 1.2
                  and mc["profitable_ratio"] >= 0.9)
        results.append({"subject_id": subject_id, "cases": cases,
                        "cost_scenarios": scenarios, "monte_carlo": mc,
                        "passes_trade_robustness_gate": passes})
    result = {"schema_version": 1,
              "decision": "PASS_TRADE_ROBUSTNESS" if any(
                  row["passes_trade_robustness_gate"] for row in results) else "REJECT_TRADE_ROBUSTNESS",
              "holdout_accessed": False, "results": results,
              "limitations": ["SQ parameter perturbation remains mandatory",
                              "small-account margin and liquidation remain mandatory"]}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temporal", type=Path, required=True)
    parser.add_argument("--portfolios", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.temporal, args.portfolios, args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
