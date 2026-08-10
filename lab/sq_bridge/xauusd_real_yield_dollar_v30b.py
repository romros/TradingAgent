#!/usr/bin/env python3
"""Macro-only frequency preflight for XAU/USD execution-sensitivity audit v30b."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any


def parameter_grid(config: dict[str, Any]) -> list[tuple[int, float, float]]:
    search = config["search"]
    points = list(itertools.product(search["lookback_weeks"],
                                    search["real_yield_change_threshold_bps"],
                                    search["broad_dollar_change_threshold_pct"]))
    if len(points) != search["attempt_budget"]:
        raise ValueError(f"attempt contract mismatch: {len(points)} != {search['attempt_budget']}")
    return points


def assert_macro_only(config: dict[str, Any]) -> None:
    forbidden = ("xau_performance_accessed", "validation_accessed", "oos_accessed",
                 "holdout_accessed", "sqcli_authorized", "paper_authorized", "live_authorized")
    if any(config.get(field) is not False for field in forbidden):
        raise ValueError("macro preflight requires performance, future periods, SQ and trading to remain sealed")


def load_series(path: Path, series: str) -> dict[date, float]:
    rows: dict[date, float] = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["observation_date", series]:
            raise ValueError(f"unexpected columns in {path}: {reader.fieldnames}")
        for raw in reader:
            stamp = date.fromisoformat(raw["observation_date"])
            value = raw[series].strip()
            if not value or value == ".":
                continue
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"non-finite {series} value on {stamp}")
            if stamp in rows:
                raise ValueError(f"duplicate {series} date: {stamp}")
            rows[stamp] = number
    if not rows:
        raise ValueError(f"empty series: {series}")
    return rows


def friday_for(stamp: date) -> date:
    return stamp + timedelta(days=(4 - stamp.weekday()) % 7)


def weekly_latest(series: dict[date, float], start: date, end: date) -> dict[date, float]:
    result: dict[date, tuple[date, float]] = {}
    for stamp, value in series.items():
        if start <= stamp <= end:
            friday = friday_for(stamp)
            if friday > end + timedelta(days=4):
                continue
            previous = result.get(friday)
            if previous is None or stamp > previous[0]:
                result[friday] = (stamp, value)
    return {friday: value for friday, (_, value) in sorted(result.items())}


def decision_time(friday: date) -> datetime:
    # The following Wednesday 00:00 UTC is after Monday's H.10 release and a
    # possible Tuesday release when Monday is a Federal holiday.
    return datetime.combine(friday + timedelta(days=5), datetime.min.time())


def states(rows: list[dict[str, Any]], lookback: int, yield_bps: float,
           dollar_pct: float) -> list[dict[str, Any]]:
    output = []
    for index in range(lookback, len(rows)):
        current, prior = rows[index], rows[index - lookback]
        yield_change_bps = (current["real_yield"] - prior["real_yield"]) * 100
        dollar_change_pct = (current["broad_dollar"] / prior["broad_dollar"] - 1) * 100
        state = 0
        if yield_change_bps <= -yield_bps and dollar_change_pct <= -dollar_pct:
            state = 1
        elif yield_change_bps >= yield_bps and dollar_change_pct >= dollar_pct:
            state = -1
        output.append({**current, "state": state, "real_yield_change_bps": yield_change_bps,
                       "broad_dollar_change_pct": dollar_change_pct})
    return output


def episodes(state_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    active = None
    for row in state_rows:
        state = row["state"]
        if active and state != active["side"]:
            result.append(active)
            active = None
        if state and active is None:
            active = {"side": state, "entry_friday": row["friday"],
                      "decision_time_utc": decision_time(row["friday"]).isoformat() + "Z",
                      "weeks": 1}
        elif state and active:
            active["weeks"] += 1
    if active:
        result.append(active)
    return result


def adjacent_neighbors(point: tuple[int, float, float], passing: set[tuple], axes: list[list]) -> int:
    count = 0
    for index, axis in enumerate(axes):
        position = axis.index(point[index])
        for neighbor in (position - 1, position + 1):
            candidate = list(point)
            if 0 <= neighbor < len(axis):
                candidate[index] = axis[neighbor]
                count += tuple(candidate) in passing
    return count


def evaluate(config: dict[str, Any], real_yield: dict[date, float],
             broad_dollar: dict[date, float], source_paths: list[Path]) -> dict[str, Any]:
    assert_macro_only(config)
    points = parameter_grid(config)
    start, end = map(date.fromisoformat, config["splits"]["train"])
    real_weekly = weekly_latest(real_yield, start, end)
    dollar_weekly = weekly_latest(broad_dollar, start, end)
    first_friday = friday_for(start)
    expected = []
    cursor = first_friday
    while cursor <= end:
        expected.append(cursor)
        cursor += timedelta(days=7)
    common = sorted(set(real_weekly) & set(dollar_weekly) & set(expected))
    rows = [{"friday": stamp, "real_yield": real_weekly[stamp],
             "broad_dollar": dollar_weekly[stamp]} for stamp in common]
    complete_ratio = len(common) / len(expected)
    gate = config["macro_frequency_gate"]
    evaluated = []
    for point in points:
        state_rows = states(rows, *point)
        runs = episodes(state_rows)
        side_counts = Counter(run["side"] for run in runs)
        years = {side: len({date.fromisoformat(run["entry_friday"]).year
                            if isinstance(run["entry_friday"], str) else run["entry_friday"].year
                            for run in runs if run["side"] == side}) for side in (1, -1)}
        exposed = sum(row["state"] != 0 for row in state_rows) / len(state_rows) if state_rows else 0
        durations = [run["weeks"] for run in runs]
        numeric = (complete_ratio >= gate["minimum_complete_week_ratio"]
                   and all(side_counts[side] >= gate["minimum_episodes_per_side"] for side in (1, -1))
                   and all(years[side] >= gate["minimum_entry_years_per_side"] for side in (1, -1))
                   and gate["minimum_exposed_week_ratio"] <= exposed <= gate["maximum_exposed_week_ratio"]
                   and bool(durations)
                   and median(durations) <= gate["maximum_median_episode_weeks"])
        evaluated.append({
            "parameters": {"lookback_weeks": point[0],
                           "real_yield_change_threshold_bps": point[1],
                           "broad_dollar_change_threshold_pct": point[2]},
            "parameter_tuple": list(point), "long_episodes": side_counts[1],
            "short_episodes": side_counts[-1], "long_entry_years": years[1],
            "short_entry_years": years[-1], "exposed_week_ratio": exposed,
            "median_episode_weeks": median(durations) if durations else None,
            "maximum_episode_weeks": max(durations) if durations else None,
            "passes_numeric_frequency_gate": numeric,
        })
    passing = {tuple(row["parameter_tuple"]) for row in evaluated
               if row["passes_numeric_frequency_gate"]}
    axes = [config["search"][key] for key in ("lookback_weeks",
                                               "real_yield_change_threshold_bps",
                                               "broad_dollar_change_threshold_pct")]
    for row in evaluated:
        row["stable_neighbors"] = adjacent_neighbors(tuple(row["parameter_tuple"]), passing, axes)
        row["passes_macro_frequency_gate"] = (row["passes_numeric_frequency_gate"]
                                                and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_macro_frequency_gate"]]
    return {
        "schema_version": 1, "campaign_id": config["campaign_id"],
        "stage": "macro_frequency_preflight",
        "decision": "PASS_TO_TRAIN_PERFORMANCE" if survivors else "REJECT_MACRO_FREQUENCY",
        "train_window": [start.isoformat(), end.isoformat()],
        "expected_train_weeks": len(expected), "complete_common_train_weeks": len(common),
        "complete_week_ratio": complete_ratio,
        "first_common_friday": common[0].isoformat() if common else None,
        "last_common_friday": common[-1].isoformat() if common else None,
        "attempted": len(evaluated), "survivor_count": len(survivors),
        "survivors": survivors, "all_results": evaluated,
        "source_files": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                         for path in source_paths],
        "information_timing": config["information_timing"],
        "xau_performance_accessed": False, "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False, "sqcli_used": False,
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.config.read_bytes()
    config = json.loads(raw)
    source_paths = [Path(config["macro_sources"][key]["path"])
                    for key in ("real_yield", "broad_dollar")]
    result = evaluate(config,
                      load_series(source_paths[0], config["macro_sources"]["real_yield"]["series"]),
                      load_series(source_paths[1], config["macro_sources"]["broad_dollar"]["series"]),
                      source_paths)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "expected_train_weeks", "complete_common_train_weeks",
                       "complete_week_ratio", "attempted", "survivor_count")}, indent=2))


if __name__ == "__main__":
    main()
