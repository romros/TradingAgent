#!/usr/bin/env python3
"""Performance-blind SPX regular-session D1 proxy parity for Alquimia v4."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from lab.sq_bridge.intraday_source_parity import load_ohlcv_parquet


NY = ZoneInfo("America/New_York")
SESSION_START = time(9, 30)
SESSION_END = time(16, 0)
EXPECTED_MINUTES = 390
MIN_SESSION_COVERAGE = 0.95


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    if left_variance == 0 or right_variance == 0:
        return None
    covariance = sum((a - left_mean) * (b - right_mean)
                     for a, b in zip(left, right))
    return covariance / math.sqrt(left_variance * right_variance)


def aggregate_regular_session(rows: list[dict]) -> tuple[dict[str, dict], dict[str, float]]:
    """Create NY cash-session bars; incomplete sessions remain visible but unusable."""
    grouped: dict[str, list[tuple[datetime, dict]]] = defaultdict(list)
    for row in rows:
        local = datetime.fromtimestamp(int(row["ts"]), timezone.utc).astimezone(NY)
        if local.weekday() < 5 and SESSION_START <= local.time() < SESSION_END:
            grouped[local.date().isoformat()].append((local, row))
    complete: dict[str, dict] = {}
    coverage: dict[str, float] = {}
    for day, members in grouped.items():
        members.sort(key=lambda item: item[0])
        unique_minutes = {item[0].replace(second=0, microsecond=0) for item in members}
        ratio = min(1.0, len(unique_minutes) / EXPECTED_MINUTES)
        coverage[day] = ratio
        if ratio < MIN_SESSION_COVERAGE:
            continue
        bars = [item[1] for item in members]
        complete[day] = {
            "open": float(bars[0]["open"]), "high": max(float(row["high"]) for row in bars),
            "low": min(float(row["low"]) for row in bars), "close": float(bars[-1]["close"]),
            "observed_minutes": len(unique_minutes), "coverage_ratio": ratio,
        }
    return complete, coverage


def compare(reference_rows: list[dict], ostium_rows: list[dict]) -> dict:
    reference, reference_coverage = aggregate_regular_session(reference_rows)
    ostium, ostium_coverage = aggregate_regular_session(ostium_rows)
    observed_starts = [min(values) for values in (reference_coverage, ostium_coverage) if values]
    observed_ends = [max(values) for values in (reference_coverage, ostium_coverage) if values]
    common_start = max(observed_starts) if len(observed_starts) == 2 else None
    common_end = min(observed_ends) if len(observed_ends) == 2 else None
    if common_start is not None and common_end is not None and common_start <= common_end:
        reference_common = {day: bar for day, bar in reference.items()
                            if common_start <= day <= common_end}
        ostium_common = {day: bar for day, bar in ostium.items()
                         if common_start <= day <= common_end}
    else:
        reference_common, ostium_common = {}, {}
    aligned = sorted(set(reference_common) & set(ostium_common))
    union = set(reference_common) | set(ostium_common)
    differences = {
        field: [abs(ostium_common[day][field] / reference_common[day][field] - 1) * 10_000
                for day in aligned]
        for field in ("open", "high", "low", "close")
    }
    reference_returns: list[float] = []
    ostium_returns: list[float] = []
    directions: list[bool] = []
    for previous, current in zip(aligned, aligned[1:]):
        reference_return = (reference_common[current]["close"]
                            / reference_common[previous]["close"] - 1)
        ostium_return = ostium_common[current]["close"] / ostium_common[previous]["close"] - 1
        reference_returns.append(reference_return)
        ostium_returns.append(ostium_return)
        if abs(reference_return) >= 1e-7 or abs(ostium_return) >= 1e-7:
            directions.append((reference_return > 0) == (ostium_return > 0))
    common_coverage = len(aligned) / len(union) if union else 0.0
    return_correlation = correlation(reference_returns, ostium_returns)
    direction_match = sum(directions) / len(directions) if directions else None
    close_p95 = percentile(differences["close"], .95)
    reasons = []
    if len(aligned) < 60:
        reasons.append("ALIGNED_COMPLETE_SESSIONS_LT_60")
    if common_coverage < .95:
        reasons.append("COMMON_COMPLETE_SESSION_COVERAGE_LT_0_95")
    if return_correlation is None or return_correlation < .99:
        reasons.append("D1_RETURN_CORRELATION_LT_0_99")
    if direction_match is None or direction_match < .95:
        reasons.append("D1_DIRECTION_MATCH_LT_0_95")
    if close_p95 is None or close_p95 > 15:
        reasons.append("D1_CLOSE_DIFF_P95_GT_15_BPS")
    return {
        "schema_version": 1,
        "performance_accessed": False,
        "session": {"timezone": "America/New_York", "start": "09:30",
                    "end_exclusive": "16:00", "expected_minutes": EXPECTED_MINUTES,
                    "minimum_session_coverage_ratio": MIN_SESSION_COVERAGE},
        "reference_sessions_observed": len(reference_coverage),
        "reference_sessions_complete": len(reference),
        "ostium_sessions_observed": len(ostium_coverage),
        "ostium_sessions_complete": len(ostium),
        "common_observed_span": {"first": common_start, "last": common_end},
        "reference_complete_sessions_in_common_span": len(reference_common),
        "ostium_complete_sessions_in_common_span": len(ostium_common),
        "aligned_complete_sessions": len(aligned),
        "first_aligned_session": aligned[0] if aligned else None,
        "last_aligned_session": aligned[-1] if aligned else None,
        "common_complete_session_coverage_ratio": common_coverage,
        "return_pairs": len(reference_returns),
        "d1_close_return_correlation": return_correlation,
        "d1_return_direction_match_ratio": direction_match,
        "difference_bps": {
            field: {"median": percentile(values, .5), "p95": percentile(values, .95),
                    "maximum": max(values) if values else None}
            for field, values in differences.items()
        },
        "decision": "PASS_D1_SOURCE_MAPPING" if not reasons else "BLOCK_D1_SOURCE_MAPPING",
        "reasons": reasons,
        "research_only": True,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, nargs="+", required=True)
    parser.add_argument("--ostium", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(load_ohlcv_parquet(args.reference), load_ohlcv_parquet(args.ostium))
    receipt = lambda path: {"path": str(path),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "bytes": path.stat().st_size}
    result["reference_files"] = [receipt(path) for path in args.reference]
    result["ostium_files"] = [receipt(path) for path in args.ostium]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "reasons": result["reasons"],
                      "aligned_complete_sessions": result["aligned_complete_sessions"]}, indent=2))


if __name__ == "__main__":
    main()
