#!/usr/bin/env python3
"""Frozen pre-OOS cross-sectional momentum screen for five IBKR ETFs."""
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
SPEC = HERE / "etf_relative_momentum_preregistration_v1.json"
LOCK = HERE / "etf_relative_momentum_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[dt.date, tuple[float, float]]:
    if "2025" in path.name or "2026" in path.name:
        raise ValueError("FUTURE_HOLDOUT_FILENAME_SEALED")
    result = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            day = dt.date.fromisoformat(row["date"])
            if day.year >= 2025:
                raise ValueError("FUTURE_HOLDOUT_ROW_SEALED")
            result[day] = (float(row["open"]), float(row["close"]))
    return result


def reviews(days: list[dt.date]) -> list[int]:
    months = {}
    for index, day in enumerate(days):
        months[(day.year, day.month)] = index
    return sorted(months.values())


def monthly_returns(frames: dict[str, dict], lookback: int,
                    start: dt.date, end: dt.date) -> list[dict]:
    days = sorted(set.intersection(*(set(frame) for frame in frames.values())))
    points = reviews(days)
    result = []
    for position, signal_index in enumerate(points[:-1]):
        if signal_index < lookback or signal_index + 1 >= len(days):
            continue
        next_signal = points[position + 1]
        if next_signal + 1 >= len(days):
            continue
        entry_day, exit_day = days[signal_index + 1], days[next_signal + 1]
        if not (start <= entry_day and exit_day <= end):
            continue
        scores = {asset: frames[asset][days[signal_index]][1] /
                  frames[asset][days[signal_index - lookback]][1] - 1.0
                  for asset in frames}
        selected = sorted((asset for asset in frames if scores[asset] > 0),
                          key=lambda asset: (-scores[asset], asset))[:2]
        sleeve_returns = [frames[asset][exit_day][0] /
                          frames[asset][entry_day][0] - 1.0 for asset in selected]
        result.append({"entry": entry_day, "exit": exit_day,
                       "return": sum(sleeve_returns) / 2.0,
                       "selected": selected, "scores": scores})
    return result


def metrics(rows: list[dict]) -> dict:
    values = [row["return"] for row in rows]
    mean = statistics.mean(values) if values else 0.0
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    equity = peak = 1.0
    drawdown = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        drawdown = max(drawdown, 1.0 - equity / peak)
    return {"monthly_observations": len(values), "total_return": equity - 1.0,
            "annualized_sharpe": mean / sd * math.sqrt(12) if sd else None,
            "maximum_drawdown": drawdown,
            "cash_slot_months": sum(2 - len(row["selected"]) for row in rows)}


def screen(assets: dict[str, Path], output: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if (sha(SPEC) != lock["preregistration_sha256"]
            or set(assets) != set(spec["assets"])):
        raise ValueError("FROZEN_CONTRACT_MISMATCH")
    frames = {name: load(path) for name, path in assets.items()}
    bounds = {name: tuple(map(dt.date.fromisoformat, value))
              for name, value in spec["periods"].items() if isinstance(value, list)}
    results = {}
    for variant in spec["rule"]["variants"]:
        results[variant["id"]] = {}
        for stage in ("train", "validation"):
            rows = monthly_returns(frames, variant["lookback_sessions"],
                                   *bounds[stage])
            results[variant["id"]][stage] = metrics(rows)
    gate = spec["validation_release_gate"]
    central = results[spec["rule"]["central_variant"]]["validation"]
    passed = (all(results[name]["validation"]["total_return"] > 0
                  for name in results)
              and (central["annualized_sharpe"] or -999)
              >= gate["central_minimum_annualized_sharpe"]
              and central["maximum_drawdown"] <= gate["central_maximum_drawdown"]
              and central["monthly_observations"] >= gate["minimum_monthly_observations"])
    report = {"schema_version": 1, "preregistration_sha256": sha(SPEC),
              "source_sha256": {name: sha(path) for name, path in assets.items()},
              "results": results,
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
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = {name: Path(path) for name, path in
              (value.split("=", 1) for value in args.asset)}
    print(json.dumps(screen(assets, args.output), indent=2))


if __name__ == "__main__":
    main()
