#!/usr/bin/env python3
"""Build a deterministic NY-17 EURUSD D1 import source for StrategyQuant."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path

import duckdb

from lab.sq_bridge.eurusd_d1_historical_coverage_v4 import source_receipt


EXPECTED_MINUTES = 1440
MINIMUM_COMPLETE_RATIO = .95


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(root: Path) -> list[tuple]:
    pattern = str(root / "year=*" / "month=*" / "data.parquet")
    return duckdb.connect(":memory:").execute(
        """WITH localized AS (
          SELECT ts, open, high, low, close, volume,
                 timezone('America/New_York', to_timestamp(ts)) AS local_ts
          FROM read_parquet(?)
        ), sessions AS (
          SELECT CASE WHEN CAST(local_ts AS TIME) >= TIME '17:00:00'
                 THEN CAST(local_ts AS DATE) + 1 ELSE CAST(local_ts AS DATE) END AS session_day,
                 count(DISTINCT ts) AS observed_minutes,
                 arg_min(open, ts) AS open, max(high) AS high, min(low) AS low,
                 arg_max(close, ts) AS close, sum(volume) AS volume
          FROM localized GROUP BY 1
        )
        SELECT session_day, observed_minutes, open, high, low, close, volume
        FROM sessions
        WHERE dayofweek(session_day) BETWEEN 1 AND 5
          AND observed_minutes >= ?
        ORDER BY session_day""", [pattern, int(EXPECTED_MINUTES * MINIMUM_COMPLETE_RATIO)]).fetchall()


def validate(rows: list[tuple]) -> None:
    if len(rows) < 5000:
        raise ValueError("fewer than 5000 complete D1 sessions")
    days = [row[0] for row in rows]
    if days != sorted(set(days)):
        raise ValueError("session dates must be unique and sorted")
    for day, minutes, open_, high, low, close, volume in rows:
        if not isinstance(day, date) or day.weekday() >= 5:
            raise ValueError("weekend session leaked into canonical D1 source")
        if int(minutes) < EXPECTED_MINUTES * MINIMUM_COMPLETE_RATIO:
            raise ValueError("incomplete session leaked into canonical D1 source")
        if not (float(low) <= min(float(open_), float(close))
                <= max(float(open_), float(close)) <= float(high)):
            raise ValueError("invalid OHLC")
        if float(volume) < 0:
            raise ValueError("negative volume")


def write_csv(path: Path, rows: list[tuple]) -> None:
    validate(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            for day, _minutes, open_, high, low, close, volume in rows:
                handle.write(f"{day:%Y.%m.%d},00:00,{float(open_):.5f},{float(high):.5f},"
                             f"{float(low):.5f},{float(close):.5f},{int(round(float(volume)))}\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def build(root: Path, output: Path) -> dict:
    rows = extract(root)
    write_csv(output, rows)
    receipt = source_receipt(root)
    return {
        "schema_version": 1, "symbol": "EURUSD", "timeframe": "D1",
        "session_timezone": "America/New_York", "session_boundary": "17:00",
        "minimum_complete_session_ratio": MINIMUM_COMPLETE_RATIO,
        "performance_accessed": False,
        "source": {key: receipt[key] for key in ("root", "files", "bytes", "manifest_sha256")},
        "output": {"path": str(output), "bytes": output.stat().st_size,
                   "sha256": sha256(output)},
        "rows": len(rows), "first": rows[0][0].isoformat(), "last": rows[-1][0].isoformat(),
        "weekend_rows": sum(row[0].weekday() >= 5 for row in rows),
        "decision": "PASS_CANONICAL_D1_IMPORT_SOURCE",
        "research_only": True, "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source_root, args.output_csv)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "decision", "rows", "first", "last", "weekend_rows")}, indent=2))


if __name__ == "__main__":
    main()
