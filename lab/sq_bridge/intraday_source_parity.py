#!/usr/bin/env python3
"""Generic M1 parity pilot between a historical proxy and clean Ostium candles."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import duckdb

from lab.sq_bridge.canonical_ohlcv import (
    aggregate_fx_daily_ny_close, aggregate_m1, complete_by_timestamp,
)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def _correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(vx * vy)


def load_parquet(paths: list[Path]) -> dict[int, float]:
    if not paths:
        return {}
    rows = duckdb.connect(":memory:").execute(
        'SELECT "ts", "close" FROM read_parquet(?) ORDER BY "ts"',
        [[str(path) for path in paths]],
    ).fetchall()
    return {int(ts): float(close) for ts, close in rows if close and float(close) > 0}


def load_ohlcv_parquet(paths: list[Path]) -> list[dict]:
    if not paths:
        return []
    rows = duckdb.connect(":memory:").execute(
        'SELECT "ts", "open", "high", "low", "close", '
        'coalesce("volume", 0) FROM read_parquet(?) ORDER BY "ts"',
        [[str(path) for path in paths]],
    ).fetchall()
    return [
        {"ts": int(ts), "open": float(open_), "high": float(high),
         "low": float(low), "close": float(close), "volume": float(volume or 0)}
        for ts, open_, high, low, close, volume in rows
    ]


def aggregate_close(rows: dict[int, float], timeframe_minutes: int) -> dict[int, float]:
    bucket_seconds = timeframe_minutes * 60
    aggregated = {}
    for timestamp, close in sorted(rows.items()):
        aggregated[(timestamp // bucket_seconds) * bucket_seconds] = close
    return aggregated


def compare(
    reference: dict[int, float], ostium: dict[int, float], interval_seconds: int = 60
) -> dict:
    timestamps = sorted(set(reference) & set(ostium))
    union = set(reference) | set(ostium)
    diffs = [abs(ostium[ts] / reference[ts] - 1) * 10_000 for ts in timestamps]
    ref_returns, ost_returns, direction = [], [], []
    for previous, current in zip(timestamps, timestamps[1:]):
        if current - previous != interval_seconds:
            continue
        rr = reference[current] / reference[previous] - 1
        ro = ostium[current] / ostium[previous] - 1
        ref_returns.append(rr)
        ost_returns.append(ro)
        if abs(rr) >= 1e-7 or abs(ro) >= 1e-7:
            direction.append((rr > 0) == (ro > 0))
    return {
        "reference_rows": len(reference),
        "ostium_rows": len(ostium),
        "aligned_rows": len(timestamps),
        "union_coverage_ratio": len(timestamps) / len(union) if union else 0,
        "first_aligned_ts": timestamps[0] if timestamps else None,
        "last_aligned_ts": timestamps[-1] if timestamps else None,
        "close_diff_bps_median": _percentile(diffs, .5),
        "close_diff_bps_p95": _percentile(diffs, .95),
        "close_diff_bps_max": max(diffs) if diffs else None,
        "m1_return_correlation": _correlation(ref_returns, ost_returns),
        "return_direction_match_ratio": sum(direction) / len(direction) if direction else None,
        "consecutive_return_pairs": len(ref_returns),
        "interval_seconds": interval_seconds,
    }


def decide(metrics: dict) -> dict:
    reasons = []
    if metrics["aligned_rows"] < 1_000:
        reasons.append("ALIGNED_ROWS_LT_1000")
    if metrics["union_coverage_ratio"] < .85:
        reasons.append("UNION_COVERAGE_LT_0_85")
    if (metrics["m1_return_correlation"] or -1) < .95:
        reasons.append("M1_RETURN_CORRELATION_LT_0_95")
    if (metrics["return_direction_match_ratio"] or 0) < .90:
        reasons.append("DIRECTION_MATCH_LT_0_90")
    if metrics["close_diff_bps_p95"] is None or metrics["close_diff_bps_p95"] > 10:
        reasons.append("CLOSE_DIFF_P95_GT_10_BPS")
    return {
        "decision": "PASS_PROXY_PILOT" if not reasons else "BLOCK",
        "reasons": reasons,
        "scope": "M1_MAPPING_PILOT_ONLY_NOT_PAPER_OR_LIVE",
    }


def decide_research_timeframe(metrics: dict, minimum_rows: int) -> dict:
    reasons = []
    if metrics["aligned_rows"] < minimum_rows:
        reasons.append(f"ALIGNED_ROWS_LT_{minimum_rows}")
    if metrics["union_coverage_ratio"] < .95:
        reasons.append("UNION_COVERAGE_LT_0_95")
    if (metrics["m1_return_correlation"] or -1) < .98:
        reasons.append("RETURN_CORRELATION_LT_0_98")
    if (metrics["return_direction_match_ratio"] or 0) < .95:
        reasons.append("DIRECTION_MATCH_LT_0_95")
    if metrics["close_diff_bps_p95"] is None or metrics["close_diff_bps_p95"] > 10:
        reasons.append("CLOSE_DIFF_P95_GT_10_BPS")
    return {"pass": not reasons, "reasons": reasons}


def decide_complete_ohlcv_timeframe(metrics: dict, minimum_rows: int) -> dict:
    """Gate a research timeframe on complete OHLC bars, never partial buckets."""
    close = metrics["close_returns"]
    if close["aligned_rows"] != metrics["aligned_complete_bars"]:
        return {"pass": False, "reasons": ["INCONSISTENT_COMPLETE_BAR_COUNTS"]}
    return decide_research_timeframe(close, minimum_rows)


def compare_bars(reference_all, ostium_all, interval_seconds: int, minimum_coverage: float = 1.0) -> dict:
    reference = complete_by_timestamp(reference_all, minimum_coverage)
    ostium = complete_by_timestamp(ostium_all, minimum_coverage)
    timestamps = sorted(set(reference) & set(ostium))
    fields = {}
    for field in ("open", "high", "low", "close"):
        differences = [
            abs(getattr(ostium[ts], field) / getattr(reference[ts], field) - 1) * 10_000
            for ts in timestamps if getattr(reference[ts], field) > 0
        ]
        fields[field] = {
            "diff_bps_median": _percentile(differences, .5),
            "diff_bps_p95": _percentile(differences, .95),
            "diff_bps_max": max(differences) if differences else None,
        }
    close_metrics = compare(
        {ts: bar.close for ts, bar in reference.items()},
        {ts: bar.close for ts, bar in ostium.items()},
        interval_seconds=interval_seconds,
    )
    return {
        "reference_bars_total": len(reference_all),
        "reference_bars_complete": len(reference),
        "ostium_bars_total": len(ostium_all),
        "ostium_bars_complete": len(ostium),
        "aligned_complete_bars": len(timestamps),
        "fields": fields,
        "close_returns": close_metrics,
    }


def compare_ohlcv(reference_rows: list[dict], ostium_rows: list[dict], minutes: int) -> dict:
    result = compare_bars(
        aggregate_m1(reference_rows, minutes),
        aggregate_m1(ostium_rows, minutes),
        interval_seconds=minutes * 60,
    )
    return {"timeframe_minutes": minutes, **result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--reference", type=Path, nargs="+", required=True)
    parser.add_argument("--ostium", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference_rows = load_ohlcv_parquet(args.reference)
    ostium_rows = load_ohlcv_parquet(args.ostium)
    reference = {row["ts"]: row["close"] for row in reference_rows}
    ostium = {row["ts"]: row["close"] for row in ostium_rows}
    timeframes = {}
    for minutes in (1, 5, 15, 60, 240):
        timeframes[str(minutes)] = compare(
            aggregate_close(reference, minutes),
            aggregate_close(ostium, minutes),
            interval_seconds=minutes * 60,
        )
    ohlcv_timeframes = {
        str(minutes): compare_ohlcv(reference_rows, ostium_rows, minutes)
        for minutes in (5, 15, 60, 240)
    }
    daily_ny_close = compare_bars(
        aggregate_fx_daily_ny_close(reference_rows),
        aggregate_fx_daily_ny_close(ostium_rows),
        interval_seconds=86_400,
        minimum_coverage=.98,
    )
    metrics = timeframes["1"]
    timeframe_decisions = {
        "M1": decide(metrics),
        "M15": decide_complete_ohlcv_timeframe(ohlcv_timeframes["15"], minimum_rows=500),
        "H1": decide_complete_ohlcv_timeframe(ohlcv_timeframes["60"], minimum_rows=40),
        "H4": decide_complete_ohlcv_timeframe(ohlcv_timeframes["240"], minimum_rows=30),
    }
    h1_pass = timeframe_decisions["H1"]["pass"]
    overall = (
        "PASS_H1_MAPPING_PILOT_EXTEND_SAMPLE"
        if h1_pass else "BLOCK_H1_MAPPING_PILOT"
    )
    result = {"schema_version": 1, "symbol": args.symbol.upper(),
              "reference_files": [str(p) for p in args.reference],
              "ostium_files": [str(p) for p in args.ostium],
              "metrics": metrics, "timeframes_minutes": timeframes,
              "ohlcv_timeframes_minutes": ohlcv_timeframes,
              "d1_new_york_17_close": daily_ny_close,
              "timeframe_decisions": timeframe_decisions,
              "decision": overall,
              "reasons": [] if h1_pass else timeframe_decisions["H1"]["reasons"],
              "scope": "H1_MAPPING_PILOT_ONLY_EXTEND_TO_30_DAYS_BEFORE_RESEARCH"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
