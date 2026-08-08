#!/usr/bin/env python3
"""Aggregate normalized Ostium snapshots and evaluate the execution-evidence gate."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def aggregate(
    snapshots: list[dict[str, Any]], *, min_open_samples: int = 30,
    min_days: int = 3, min_utc_hours: int = 6,
) -> dict[str, Any]:
    valid = [row for row in snapshots if row.get("instrument", {}).get("pair_id") == "10"]
    opened = [row for row in valid if row.get("market_state", {}).get("is_market_open") is True]
    timestamps = [datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")) for row in opened]
    days = sorted({stamp.date().isoformat() for stamp in timestamps})
    hours = sorted({stamp.hour for stamp in timestamps})
    spreads = [float(row["quote"]["spread_bps"]) for row in opened]

    by_notional: dict[str, dict[str, list[float]]] = {}
    for row in opened:
        for side in ("long", "short"):
            for point in row.get("simulated_slippage", {}).get(side, []):
                key = format(float(point["notional_usd"]), "g")
                by_notional.setdefault(key, {"long": [], "short": []})[side].append(
                    float(point["slippage_bps"])
                )
    slippage = {}
    for notional, sides in sorted(by_notional.items(), key=lambda item: float(item[0])):
        slippage[notional] = {
            side: {"p50_bps": percentile(values, .5), "p95_bps": percentile(values, .95), "n": len(values)}
            for side, values in sides.items()
        }

    checks = {
        "open_samples": {"actual": len(opened), "required": min_open_samples, "pass": len(opened) >= min_open_samples},
        "distinct_utc_days": {"actual": len(days), "required": min_days, "pass": len(days) >= min_days},
        "distinct_utc_hours": {"actual": len(hours), "required": min_utc_hours, "pass": len(hours) >= min_utc_hours},
    }
    gate_pass = all(check["pass"] for check in checks.values())
    return {
        "schema_version": 1,
        "instrument": "Ostium US500/USD (pair 10)",
        "all_valid_snapshots": len(valid),
        "open_market_snapshots": len(opened),
        "observed_utc_days": days,
        "observed_utc_hours": hours,
        "spread_bps": {"p50": percentile(spreads, .5), "p95": percentile(spreads, .95), "max": max(spreads) if spreads else None},
        "slippage_by_notional": slippage,
        "gate": {
            "checks": checks,
            "execution_economics": "PASS" if gate_pass else "INSUFFICIENT_OPEN_MARKET_EVIDENCE",
            "paper": "BLOCKED" if not gate_pass else "REQUIRES_STRATEGY_OOS_AND_MAE_GATES",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-open-samples", type=int, default=30)
    parser.add_argument("--min-days", type=int, default=3)
    parser.add_argument("--min-utc-hours", type=int, default=6)
    args = parser.parse_args()
    snapshots = [json.loads(path.read_text()) for path in args.paths]
    result = aggregate(snapshots, min_open_samples=args.min_open_samples, min_days=args.min_days,
                       min_utc_hours=args.min_utc_hours)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
