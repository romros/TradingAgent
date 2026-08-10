#!/usr/bin/env python3
"""Audit a full SQ EURUSD D1 export against Dukascopy and session hygiene."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import duckdb

from lab.sq_bridge.eurusd_d1_historical_coverage_v4 import source_receipt


OHLC_TOLERANCE = 1e-5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_sq(path: Path) -> dict[str, list[float]]:
    rows = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 6:
                continue
            try:
                day = datetime.strptime(row[0], "%Y.%m.%d").date().isoformat()
                values = [float(row[index]) for index in range(2, 6)]
            except ValueError:
                continue
            if day in rows:
                raise ValueError(f"duplicate SQ D1 date: {day}")
            rows[day] = values
    if not rows:
        raise ValueError("SQ D1 export is empty")
    return rows


def aggregate_source(root: Path) -> dict[str, dict]:
    pattern = str(root / "year=*" / "month=*" / "data.parquet")
    rows = duckdb.connect(":memory:").execute(
        """WITH localized AS (
          SELECT ts, open, high, low, close,
                 CAST(timezone('Etc/GMT+5', to_timestamp(ts)) AS DATE) AS day
          FROM read_parquet(?)
        )
        SELECT day, count(DISTINCT ts), arg_min(open, ts), max(high), min(low),
               arg_max(close, ts)
        FROM localized GROUP BY day ORDER BY day""", [pattern]).fetchall()
    return {day.isoformat(): {"minutes": int(minutes),
            "ohlc": [float(open_), float(high), float(low), float(close)]}
            for day, minutes, open_, high, low, close in rows}


def evaluate(sq: dict[str, list[float]], source: dict[str, dict]) -> dict:
    common = sorted(set(sq) & set(source))
    deltas = {day: max(abs(sq[day][index] - source[day]["ohlc"][index])
                       for index in range(4)) for day in common}
    matched = sum(delta <= OHLC_TOLERANCE for delta in deltas.values())
    sundays = sorted(day for day in sq if datetime.fromisoformat(day).weekday() == 6)
    low_minute_days = sorted(day for day in common if source[day]["minutes"] < 1368)
    checks = {
        "minimum_rows": len(sq) >= 5000,
        "source_coverage": len(common) / len(sq) >= .99,
        "ohlc_match": matched / len(common) >= .99 if common else False,
        "no_sunday_fragments": len(sundays) == 0,
        "complete_daily_bars": len(low_minute_days) == 0,
    }
    return {
        "schema_version": 1, "symbol": "EURUSD_M1_dukas_M1_UTCMinus05",
        "timeframe": "D1", "aggregation_timezone": "fixed UTC-05:00",
        "performance_accessed": False,
        "sq_rows": len(sq), "source_rows": len(source), "common_rows": len(common),
        "source_coverage_ratio": len(common) / len(sq),
        "ohlc_match_ratio": matched / len(common) if common else 0,
        "maximum_ohlc_delta": max(deltas.values()) if deltas else None,
        "sunday_fragment_bars": len(sundays),
        "sunday_fragment_examples": sundays[:12],
        "bars_below_95pct_minutes": len(low_minute_days),
        "low_minute_examples": low_minute_days[:12],
        "checks": checks,
        "decision": "PASS_SQ_D1_RESOURCE" if all(checks.values())
                    else "BLOCK_SQ_D1_RESOURCE_SESSION",
        "research_authorized": all(checks.values()),
        "paper_authorized": False, "live_authorized": False,
    }


def audit(sq_path: Path, source_root: Path) -> dict:
    result = evaluate(read_sq(sq_path), aggregate_source(source_root))
    receipt = source_receipt(source_root)
    result["sq_export"] = {"path": str(sq_path), "bytes": sq_path.stat().st_size,
                           "sha256": sha256(sq_path)}
    result["source"] = {key: receipt[key] for key in (
        "root", "files", "bytes", "manifest_sha256")}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sq-export", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.sq_export, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"],
                      "sq_rows": result["sq_rows"],
                      "sunday_fragment_bars": result["sunday_fragment_bars"]}, indent=2))


if __name__ == "__main__":
    main()
