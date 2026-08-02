#!/usr/bin/env python3
"""Compare Builder runs without confusing attempts, survivors, and wall-clock."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median


FROZEN_FIELDS = ("data_sha256", "search_space_sha256", "filters_sha256", "engine", "timeframe")


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(run: dict) -> dict:
    attempted = run.get("attempted")
    strategies = run.get("strategies", [])
    metrics = sorted({key for row in strategies for key, value in row.get("metrics", {}).items() if isinstance(value, (int, float))})
    distributions = {}
    for metric in metrics:
        values = [float(row["metrics"][metric]) for row in strategies if isinstance(row.get("metrics", {}).get(metric), (int, float))]
        distributions[metric] = {
            "n": len(values),
            "min": min(values),
            "p25": quantile(values, 0.25),
            "median": median(values),
            "p75": quantile(values, 0.75),
            "max": max(values),
        }
    return {
        "method": run.get("method"),
        "attempted": attempted,
        "accepted": len(strategies),
        "acceptance_rate": len(strategies) / attempted if isinstance(attempted, int) and attempted > 0 else None,
        "wall_clock_seconds": run.get("wall_clock_seconds"),
        "distributions": distributions,
    }


def compare(left: dict, right: dict, contract: str) -> dict:
    reasons = []
    mismatches = {field: [left.get(field), right.get(field)] for field in FROZEN_FIELDS if left.get(field) != right.get(field)}
    if mismatches:
        reasons.append("frozen_context_mismatch")
    if left.get("method") == right.get("method"):
        reasons.append("methods_not_distinct")
    if contract == "equal_attempts":
        if not isinstance(left.get("attempted"), int) or not isinstance(right.get("attempted"), int):
            reasons.append("attempt_count_missing")
        elif left["attempted"] != right["attempted"]:
            reasons.append("attempt_budget_mismatch")
    elif contract == "equal_wall_clock":
        if not isinstance(left.get("wall_clock_seconds"), (int, float)) or not isinstance(right.get("wall_clock_seconds"), (int, float)):
            reasons.append("wall_clock_missing")
        elif abs(left["wall_clock_seconds"] - right["wall_clock_seconds"]) > 1:
            reasons.append("wall_clock_budget_mismatch")
    else:
        reasons.append("unknown_contract")
    return {
        "comparable": not reasons,
        "decision": "COMPARE_DISTRIBUTIONS" if not reasons else "REJECT_COMPARISON",
        "contract": contract,
        "reasons": reasons,
        "frozen_context_mismatches": mismatches,
        "runs": [summarize(left), summarize(right)],
        "warning": "Survivors are outputs, not the search budget.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--contract", choices=("equal_attempts", "equal_wall_clock"), default="equal_attempts")
    args = parser.parse_args()
    result = compare(json.loads(args.left.read_text()), json.loads(args.right.read_text()), args.contract)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["comparable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
