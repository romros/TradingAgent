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
    min_days: int = 3, min_utc_hours: int = 6, pair_id: str | None = None,
) -> dict[str, Any]:
    present_pair_ids = {
        str(row.get("instrument", {}).get("pair_id"))
        for row in snapshots if row.get("instrument", {}).get("pair_id") is not None
    }
    if pair_id is None:
        if len(present_pair_ids) != 1:
            raise ValueError(f"snapshots must contain exactly one pair_id, found {sorted(present_pair_ids)}")
        pair_id = next(iter(present_pair_ids))
    pair_id = str(pair_id)
    valid = [row for row in snapshots if str(row.get("instrument", {}).get("pair_id")) == pair_id]
    if not valid:
        raise ValueError(f"no snapshots found for pair_id={pair_id}")
    identities = {
        (row["instrument"].get("pair_from"), row["instrument"].get("pair_to"),
         row["instrument"].get("category")) for row in valid
    }
    if len(identities) != 1:
        raise ValueError(f"instrument identity drift for pair_id={pair_id}: {sorted(identities)}")
    pair_from, pair_to, category = next(iter(identities))
    opened = [row for row in valid if row.get("market_state", {}).get("is_market_open") is True]
    timestamps = [datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00")) for row in opened]
    days = sorted({stamp.date().isoformat() for stamp in timestamps})
    hours = sorted({stamp.hour for stamp in timestamps})
    spreads = [float(row["quote"]["spread_bps"]) for row in opened]

    def distribution(values: list[float]) -> dict[str, float | int | None]:
        return {
            "n": len(values), "p50": percentile(values, .5), "p95": percentile(values, .95),
            "min": min(values) if values else None, "max": max(values) if values else None,
        }

    fee_fields = ("open_fee_bps", "close_fee_bps", "rollover_long_pct_per_8h",
                  "rollover_short_pct_per_8h")
    fee_distributions = {
        field: distribution([float(row["fees"][field]) for row in opened])
        for field in fee_fields
    }
    limit_fields = ("min_notional_usd", "max_leverage", "overnight_max_leverage")
    limit_distributions = {
        field: distribution([float(row["limits"][field]) for row in opened])
        for field in limit_fields
    }

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
        "instrument": {
            "pair_id": pair_id, "pair_from": pair_from, "pair_to": pair_to,
            "category": category,
        },
        "all_valid_snapshots": len(valid),
        "open_market_snapshots": len(opened),
        "first_open_capture_at": min((row["captured_at"] for row in opened), default=None),
        "last_open_capture_at": max((row["captured_at"] for row in opened), default=None),
        "source_raw_sha256": sorted({
            row.get("source", {}).get("raw_sha256") for row in valid
            if row.get("source", {}).get("raw_sha256")
        }),
        "observed_utc_days": days,
        "observed_utc_hours": hours,
        "spread_bps": {"p50": percentile(spreads, .5), "p95": percentile(spreads, .95), "max": max(spreads) if spreads else None},
        "slippage_by_notional": slippage,
        "fees": fee_distributions,
        "limits": limit_distributions,
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
    parser.add_argument("--pair-id", help="Expected Ostium pair id; inferred only for a single-pair input")
    args = parser.parse_args()
    snapshots = [json.loads(path.read_text()) for path in args.paths]
    result = aggregate(snapshots, min_open_samples=args.min_open_samples, min_days=args.min_days,
                       min_utc_hours=args.min_utc_hours, pair_id=args.pair_id)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
