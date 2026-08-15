#!/usr/bin/env python3
"""Frozen pre-OOS screen of canonical 12-1 ETF momentum."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.etf_relative_momentum_screen_v1 import load, metrics, reviews, sha

HERE = Path(__file__).resolve().parent
SPEC = HERE / "etf_twelve_one_momentum_preregistration_v1.json"
LOCK = HERE / "etf_twelve_one_momentum_preregistration_v1.lock.json"


def monthly_returns(frames: dict[str, dict], start: dt.date,
                    end: dt.date) -> list[dict]:
    days = sorted(set.intersection(*(set(frame) for frame in frames.values())))
    points = reviews(days)
    result = []
    for position, signal in enumerate(points[:-1]):
        if signal < 252 or signal - 21 < 0 or signal + 1 >= len(days):
            continue
        next_signal = points[position + 1]
        if next_signal + 1 >= len(days):
            continue
        entry, exit_day = days[signal + 1], days[next_signal + 1]
        if not (start <= entry and exit_day <= end):
            continue
        scores = {asset: frames[asset][days[signal - 21]][1] /
                  frames[asset][days[signal - 252]][1] - 1.0
                  for asset in frames}
        winner = min(frames, key=lambda asset: (-scores[asset], asset))
        selected = [winner] if scores[winner] > 0 else []
        value = (frames[winner][exit_day][0] / frames[winner][entry][0] - 1.0
                 if selected else 0.0)
        result.append({"entry": entry, "exit": exit_day, "return": value,
                       "selected": selected, "scores": scores})
    return result


def one_sleeve_metrics(rows: list[dict]) -> dict:
    result = metrics(rows)
    result.pop("cash_slot_months", None)
    result["cash_months"] = sum(not row["selected"] for row in rows)
    return result


def screen(assets: dict[str, Path], output: Path) -> dict:
    spec, lock = json.loads(SPEC.read_text()), json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"] or set(assets) != set(spec["assets"]):
        raise ValueError("FROZEN_CONTRACT_MISMATCH")
    frames = {name: load(path) for name, path in assets.items()}
    bounds = {name: tuple(map(dt.date.fromisoformat, value))
              for name, value in spec["periods"].items() if isinstance(value, list)}
    results = {stage: one_sleeve_metrics(monthly_returns(frames, *bounds[stage]))
               for stage in ("train", "validation")}
    gate, validation = spec["validation_release_gate"], results["validation"]
    passed = (validation["total_return"] > gate["minimum_total_return"]
              and (validation["annualized_sharpe"] or -999) >= gate["minimum_annualized_sharpe"]
              and validation["maximum_drawdown"] <= gate["maximum_drawdown"]
              and validation["monthly_observations"] >= gate["minimum_monthly_observations"])
    report = {"schema_version": 1,
              "decision": ("PASS_VALIDATION_FREEZE_BEFORE_OOS" if passed else "REJECT_VALIDATION"),
              "preregistration_sha256": sha(SPEC),
              "source_sha256": {name: sha(path) for name, path in assets.items()},
              "results": results, "oos_2024_performance_accessed": False,
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
