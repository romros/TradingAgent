#!/usr/bin/env python3
"""Aggregate normalized Ostium snapshots and evaluate the execution-evidence gate."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
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
    minimum_sample_spacing_seconds: int = 900,
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
    raw_opened = [row for row in valid
                  if row.get("market_state", {}).get("is_market_open") is True]
    if (not isinstance(minimum_sample_spacing_seconds, int)
            or isinstance(minimum_sample_spacing_seconds, bool)
            or minimum_sample_spacing_seconds < 1):
        raise ValueError("minimum sample spacing must be a positive integer")
    by_timestamp: dict[datetime, dict[str, Any]] = {}
    exact_duplicates = 0
    for row in raw_opened:
        try:
            stamp = datetime.fromisoformat(row["captured_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid captured_at") from exc
        if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            raise ValueError("captured_at must be UTC")
        previous = by_timestamp.get(stamp)
        if previous is not None:
            if previous != row:
                raise ValueError(f"conflicting snapshots at captured_at={row['captured_at']}")
            exact_duplicates += 1
            continue
        by_timestamp[stamp] = row
    opened, timestamps, last = [], [], None
    spacing_rejections = 0
    for stamp, row in sorted(by_timestamp.items()):
        if last is not None and (stamp - last).total_seconds() < minimum_sample_spacing_seconds:
            spacing_rejections += 1
            continue
        opened.append(row)
        timestamps.append(stamp)
        last = stamp
    independent_raw_hashes = []
    for row in opened:
        digest = (row.get("source") or {}).get("raw_sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)):
            raise ValueError("each independent snapshot requires a lowercase raw SHA-256")
        independent_raw_hashes.append(digest)
    if len(set(independent_raw_hashes)) != len(independent_raw_hashes):
        raise ValueError("independent snapshots reuse a raw SHA-256")
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
    roundtrip_by_notional: dict[str, dict[str, list[float]]] = {}
    for row in opened:
        row_points: dict[str, dict[str, float]] = {"long": {}, "short": {}}
        for side in ("long", "short"):
            for point in row.get("simulated_slippage", {}).get(side, []):
                key = format(float(point["notional_usd"]), "g")
                value = float(point["slippage_bps"])
                by_notional.setdefault(key, {"long": [], "short": []})[side].append(value)
                row_points[side][key] = value
        if set(row_points["long"]) != set(row_points["short"]):
            raise ValueError("long/short slippage notionals do not match")
        fees = float(row["fees"]["open_fee_bps"]) + float(row["fees"]["close_fee_bps"])
        for key in row_points["long"]:
            long_slip, short_slip = row_points["long"][key], row_points["short"][key]
            routes = roundtrip_by_notional.setdefault(
                key, {"direction_neutral": [], "long": [], "short": []})
            # SDK priceImpactP already contains the bid/ask component. An open
            # and its eventual close consume opposing execution sides, so the
            # only observable round-trip proxy is long-open + short-open.
            roundtrip = fees + long_slip + short_slip
            routes["direction_neutral"].append(roundtrip)
            routes["long"].append(roundtrip)
            routes["short"].append(roundtrip)
    slippage = {}
    for notional, sides in sorted(by_notional.items(), key=lambda item: float(item[0])):
        slippage[notional] = {
            side: {"p50_bps": percentile(values, .5), "p95_bps": percentile(values, .95), "n": len(values)}
            for side, values in sides.items()
        }
    roundtrip = {
        notional: {side: distribution(values) for side, values in sides.items()}
        for notional, sides in sorted(
            roundtrip_by_notional.items(), key=lambda item: float(item[0]))
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
        "raw_open_market_snapshots": len(raw_opened),
        "open_market_snapshots": len(opened),
        "independence_filter": {
            "minimum_sample_spacing_seconds": minimum_sample_spacing_seconds,
            "exact_duplicate_snapshots_ignored": exact_duplicates,
            "too_close_snapshots_ignored": spacing_rejections,
        },
        "first_open_capture_at": min((row["captured_at"] for row in opened), default=None),
        "last_open_capture_at": max((row["captured_at"] for row in opened), default=None),
        "source_raw_sha256": sorted({
            row.get("source", {}).get("raw_sha256") for row in valid
            if row.get("source", {}).get("raw_sha256")
        }),
        "independent_source_raw_sha256": sorted(independent_raw_hashes),
        "observed_utc_days": days,
        "observed_utc_hours": hours,
        "spread_bps": {"p50": percentile(spreads, .5), "p95": percentile(spreads, .95), "max": max(spreads) if spreads else None},
        "slippage_by_notional": slippage,
        "roundtrip_proxy_bps_by_notional": roundtrip,
        "fees": fee_distributions,
        "limits": limit_distributions,
        "gate": {
            "checks": checks,
            "execution_economics": "PASS" if gate_pass else "INSUFFICIENT_OPEN_MARKET_EVIDENCE",
            "paper": "BLOCKED" if not gate_pass else "REQUIRES_STRATEGY_OOS_AND_MAE_GATES",
        },
        "cost_model": {
            "unit": "basis_points_of_notional",
            "direction_neutral_formula": "open_fee + close_fee + long_open_price_impact + short_open_price_impact",
            "route_formula": "same opposing-side proxy for long and short round-trips",
            "spread_semantics": "SDK priceImpactP already includes its bid/ask component; separately observed spread is diagnostic only",
            "limitation": "SDK quote and simulated-slippage proxy, not observed fills",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-open-samples", type=int, default=30)
    parser.add_argument("--min-days", type=int, default=3)
    parser.add_argument("--min-utc-hours", type=int, default=6)
    parser.add_argument("--minimum-sample-spacing-seconds", type=int, default=900)
    parser.add_argument("--pair-id", help="Expected Ostium pair id; inferred only for a single-pair input")
    args = parser.parse_args()
    snapshots = [json.loads(path.read_text()) for path in args.paths]
    result = aggregate(snapshots, min_open_samples=args.min_open_samples, min_days=args.min_days,
                       min_utc_hours=args.min_utc_hours, pair_id=args.pair_id,
                       minimum_sample_spacing_seconds=args.minimum_sample_spacing_seconds)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
