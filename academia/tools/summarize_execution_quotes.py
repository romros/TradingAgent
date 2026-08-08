#!/usr/bin/env python3
"""Summarize normalized executable quotes without storing a raw market feed."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median


REQUIRED_WINDOWS = {"open", "midday", "close"}


def _finite(value: object, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile without values")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(rows: list[dict], *, min_days: int = 3, min_per_window: int = 20) -> dict:
    accepted: list[dict] = []
    rejected = Counter()
    for row in rows:
        if row.get("instrument") not in {"US500/USD", "SPX/USD"}:
            rejected["wrong_instrument"] += 1
            continue
        if row.get("is_market_open") is not True:
            rejected["market_closed"] += 1
            continue
        window = row.get("session_window")
        if window not in REQUIRED_WINDOWS:
            rejected["invalid_session_window"] += 1
            continue
        try:
            captured = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00"))
            mid = _finite(row.get("mid"), "mid")
            bid = _finite(row.get("bid"), "bid")
            ask = _finite(row.get("ask"), "ask")
        except (KeyError, ValueError):
            rejected["invalid_quote"] += 1
            continue
        if not 0 < bid <= mid <= ask:
            rejected["invalid_quote"] += 1
            continue
        accepted.append({
            "day": captured.date().isoformat(),
            "window": window,
            "spread_bps": (ask - bid) / mid * 10_000,
        })

    spreads = [row["spread_bps"] for row in accepted]
    window_counts = Counter(row["window"] for row in accepted)
    days = sorted({row["day"] for row in accepted})
    coverage_pass = len(days) >= min_days and all(
        window_counts[window] >= min_per_window for window in REQUIRED_WINDOWS
    )
    return {
        "schema_version": 1,
        "accepted_samples": len(accepted),
        "rejected_samples": dict(sorted(rejected.items())),
        "distinct_open_days": len(days),
        "samples_by_window": {window: window_counts[window] for window in sorted(REQUIRED_WINDOWS)},
        "frozen_coverage_gate": {
            "minimum_distinct_open_days": min_days,
            "minimum_samples_per_window": min_per_window,
            "pass": coverage_pass,
        },
        "spread_bps": None if not spreads else {
            "median": median(spreads),
            "p90": percentile(spreads, 0.90),
            "p95": percentile(spreads, 0.95),
            "maximum": max(spreads),
        },
        "decision": "MEASURED" if coverage_pass else "INSUFFICIENT_OPEN_SESSION_COVERAGE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL normalized quote samples")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-days", type=int, default=3)
    parser.add_argument("--min-per-window", type=int, default=20)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    result = summarize(rows, min_days=args.min_days, min_per_window=args.min_per_window)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
