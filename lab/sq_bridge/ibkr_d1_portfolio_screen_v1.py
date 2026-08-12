#!/usr/bin/env python3
"""Screen equal-unit D1 candidate portfolios without touching the final holdout."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def load_trades(row: dict) -> list[dict]:
    path = Path(row["orders_csv_path"])
    if sha(path) != row["orders_csv_sha256"]:
        raise ValueError(f"orders hash mismatch: {path}")
    trades = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for item in csv.DictReader(handle, delimiter=";"):
            trades.append({
                "case": row["case"],
                "open": datetime.strptime(item["Open time"], "%Y.%m.%d %H:%M:%S").date(),
                "close": datetime.strptime(item["Close time"], "%Y.%m.%d %H:%M:%S").date(),
                "pnl": number(item["Profit/Loss"]) - float(row["round_trip_cost"]),
            })
    return trades


def pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    lm, rm = sum(left) / len(left), sum(right) / len(right)
    num = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    den = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return num / den if den else 0.0


def segment_metrics(trades: list[dict], start: date, end: date) -> dict:
    selected = [row for row in trades if start <= row["close"] <= end]
    daily = defaultdict(float)
    for row in selected:
        daily[row["close"]] += row["pnl"]
    pnl = [daily[key] for key in sorted(daily)]
    gp, gl = sum(max(0, value) for value in pnl), -sum(min(0, value) for value in pnl)
    equity = peak = drawdown = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "trades": len(selected), "active_close_days": len(pnl),
        "net_profit": round(sum(pnl), 2),
        "daily_profit_factor": round(gp / gl, 4) if gl else None,
        "expectancy_per_trade": round(sum(pnl) / len(selected), 2) if selected else None,
        "maximum_closed_day_drawdown": round(drawdown, 2),
    }


def maximum_concurrent(trades: list[dict]) -> int:
    events = []
    for row in trades:
        events.extend(((row["open"], 1), (row["close"] + timedelta(days=1), -1)))
    current = maximum = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        current += delta
        maximum = max(maximum, current)
    return maximum


def build(report_path: Path, output: Path, max_size: int = 3) -> dict:
    report = json.loads(report_path.read_text())
    if report.get("holdout_accessed") is not False or len(report.get("results", [])) < 2:
        raise ValueError("temporal report is not portfolio-screenable")
    candidates = {row["case"]: row for row in report["results"]}
    trades = {case: load_trades(row) for case, row in candidates.items()}
    # Dates are deliberately duplicated here from the sealed D1 split, never
    # inferred from performance and never include the final holdout.
    periods = {
        "validation": (date(2022, 4, 7), date(2023, 12, 19)),
        "oos": (date(2023, 12, 20), date(2025, 9, 1)),
    }
    rows = []
    for size in range(2, min(max_size, len(candidates)) + 1):
        for cases in itertools.combinations(sorted(candidates), size):
            combined = [trade for case in cases for trade in trades[case]]
            correlations = []
            all_dates = sorted({trade["close"] for row in trades.values() for trade in row})
            series = {}
            for case in cases:
                values = defaultdict(float)
                for trade in trades[case]:
                    values[trade["close"]] += trade["pnl"]
                series[case] = [values[day] for day in all_dates]
            for left, right in itertools.combinations(cases, 2):
                correlations.append(pearson(series[left], series[right]))
            measured = {name: segment_metrics(combined, *dates)
                        for name, dates in periods.items()}
            positive_years = []
            for year in range(2018, 2026):
                value = sum(trade["pnl"] for trade in combined if trade["close"].year == year)
                positive_years.append(value > 0)
            passes = (
                measured["validation"]["trades"] >= 40
                and measured["oos"]["trades"] >= 40
                and (measured["validation"]["daily_profit_factor"] or 0) >= 1.2
                and (measured["oos"]["daily_profit_factor"] or 0) >= 1.2
                and sum(positive_years) / len(positive_years) >= 0.7
                and max((abs(value) for value in correlations), default=0) <= 0.65
            )
            rows.append({
                "portfolio_id": "+".join(cases), "cases": list(cases),
                "size": size, "segments": measured,
                "maximum_absolute_pairwise_daily_pnl_correlation": round(
                    max((abs(value) for value in correlations), default=0), 4),
                "maximum_concurrent_positions": maximum_concurrent(combined),
                "positive_year_ratio": round(sum(positive_years) / len(positive_years), 4),
                "passes_temporal_portfolio_gate": passes,
            })
    passing = [row for row in rows if row["passes_temporal_portfolio_gate"]]
    passing.sort(key=lambda row: (
        row["segments"]["validation"]["daily_profit_factor"],
        row["segments"]["oos"]["daily_profit_factor"],
        -row["maximum_absolute_pairwise_daily_pnl_correlation"]), reverse=True)
    result = {
        "schema_version": 1,
        "decision": "PASS_TEMPORAL_PORTFOLIOS" if passing else "REJECT_TEMPORAL_PORTFOLIOS",
        "source_report_path": str(report_path.resolve()),
        "source_report_sha256": sha(report_path),
        "holdout_accessed": False,
        "portfolio_count": len(rows), "passing_count": len(passing),
        "passing_portfolios": passing,
        "all_portfolios": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-size", type=int, default=3)
    args = parser.parse_args()
    result = build(args.report, args.output, args.max_size)
    print(json.dumps({key: result[key] for key in (
        "decision", "portfolio_count", "passing_count", "passing_portfolios")}, indent=2))


if __name__ == "__main__":
    main()
