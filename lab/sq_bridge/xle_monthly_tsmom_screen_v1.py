#!/usr/bin/env python3
"""Frozen pre-OOS screen for XLE monthly time-series momentum."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE / "xle_monthly_tsmom_preregistration_v1.json"
LOCK = HERE / "xle_monthly_tsmom_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> list[dict]:
    if "2025" in path.name or "2026" in path.name:
        raise ValueError("FUTURE_HOLDOUT_FILENAME_SEALED")
    rows = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            day = dt.date.fromisoformat(row["date"])
            if day.year >= 2025:
                raise ValueError("FUTURE_HOLDOUT_ROW_SEALED")
            rows.append({"date": day, "open": float(row["open"]),
                         "close": float(row["close"])})
    return rows


def monthly_reviews(rows: list[dict]) -> list[int]:
    months = {}
    for index, row in enumerate(rows):
        months[(row["date"].year, row["date"].month)] = index
    return sorted(months.values())


def returns(rows: list[dict], lookback: int, start: dt.date,
            end: dt.date) -> list[dict]:
    reviews = monthly_reviews(rows)
    position = None
    result = []
    for review in reviews:
        if review < lookback or review + 1 >= len(rows):
            continue
        entry_index = review + 1
        day = rows[entry_index]["date"]
        desired = rows[review]["close"] > rows[review - lookback]["close"]
        if position is None and desired and start <= day <= end:
            position = {"entry": day, "price": rows[entry_index]["open"]}
        elif position is not None and not desired:
            if day <= end:
                result.append({"entry": position["entry"], "exit": day,
                               "return": rows[entry_index]["open"] / position["price"] - 1.0})
            position = None
        if day > end:
            break
    if position is not None:
        last = next(row for row in reversed(rows) if row["date"] <= end)
        result.append({"entry": position["entry"], "exit": last["date"],
                       "return": last["close"] / position["price"] - 1.0})
    return result


def metrics(trades: list[dict], start: dt.date, end: dt.date) -> dict:
    by_month = {}
    for trade in trades:
        by_month.setdefault((trade["exit"].year, trade["exit"].month), 0.0)
        by_month[(trade["exit"].year, trade["exit"].month)] += trade["return"]
    # Flat months are observations too: they are part of a long/cash strategy.
    months = []
    cursor = dt.date(start.year, start.month, 1)
    while cursor <= end:
        months.append(by_month.get((cursor.year, cursor.month), 0.0))
        cursor = (dt.date(cursor.year + 1, 1, 1) if cursor.month == 12
                  else dt.date(cursor.year, cursor.month + 1, 1))
    mean = statistics.mean(months) if months else 0.0
    sd = statistics.stdev(months) if len(months) > 1 else 0.0
    equity = peak = 1.0
    drawdown = 0.0
    for trade in trades:
        equity *= 1.0 + trade["return"]
        peak = max(peak, equity)
        drawdown = max(drawdown, 1.0 - equity / peak)
    return {"completed_trades": len(trades), "monthly_observations": len(months),
            "total_return": equity - 1.0,
            "annualized_monthly_sharpe": mean / sd * math.sqrt(12) if sd else None,
            "maximum_drawdown": drawdown}


def screen(source: Path, output: Path, spec_path: Path = SPEC,
           lock_path: Path = LOCK) -> dict:
    spec = json.loads(spec_path.read_text())
    lock = json.loads(lock_path.read_text())
    if sha(spec_path) != lock["preregistration_sha256"]:
        raise ValueError("PREREGISTRATION_LOCK_MISMATCH")
    rows = load(source)
    bounds = {name: tuple(map(dt.date.fromisoformat, value))
              for name, value in spec["periods"].items() if isinstance(value, list)}
    result = {}
    for variant in spec["variants"]:
        result[variant["id"]] = {}
        for stage in ("train", "validation"):
            start, end = bounds[stage]
            trades = returns(rows, variant["lookback_sessions"], start, end)
            result[variant["id"]][stage] = metrics(trades, start, end)
    gate = spec["validation_release_gate"]
    central = result["M12"]["validation"]
    passed = (all(result[name]["validation"]["total_return"] > 0
                  for name in ("M6", "M12"))
              and (central["annualized_monthly_sharpe"] or -999)
              >= gate["central_M12_minimum_sharpe"]
              and central["maximum_drawdown"] <= gate["central_M12_maximum_drawdown"]
              and central["monthly_observations"]
              >= gate["central_M12_minimum_monthly_observations"])
    report = {"schema_version": 1, "preregistration_sha256": sha(spec_path),
              "source_sha256": sha(source), "results": result,
              "decision": ("PASS_VALIDATION_FREEZE_BEFORE_OOS" if passed
                           else "REJECT_VALIDATION"),
              "oos_2024_performance_accessed": False,
              "holdout_2025_plus_accessed": False,
              "paper_authorized": False, "live_authorized": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=SPEC)
    parser.add_argument("--lock", type=Path, default=LOCK)
    args = parser.parse_args()
    print(json.dumps(screen(args.source, args.output, args.spec, args.lock), indent=2))


if __name__ == "__main__":
    main()
