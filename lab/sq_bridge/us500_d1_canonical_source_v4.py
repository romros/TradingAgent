#!/usr/bin/env python3
"""Build a coverage-selected US500 D1 source without consulting performance."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import duckdb

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def extract(source: Path, first: date, last: date) -> list[tuple]:
    return duckdb.connect(":memory:").execute(
        """WITH localized AS (
          SELECT timezone('America/New_York', to_timestamp(ts)) AS local_ts,
                 open, high, low, close, volume
          FROM read_parquet(?)
        ), regular AS (
          SELECT CAST(local_ts AS DATE) AS day, local_ts, open, high, low, close, volume
          FROM localized
          WHERE CAST(local_ts AS TIME) >= TIME '09:30:00'
            AND CAST(local_ts AS TIME) < TIME '16:00:00'
            AND dayofweek(CAST(local_ts AS DATE)) BETWEEN 1 AND 5
            AND CAST(local_ts AS DATE) BETWEEN ? AND ?
        )
        SELECT day, arg_min(open, local_ts) AS open, max(high) AS high,
               min(low) AS low, arg_max(close, local_ts) AS close,
               sum(volume) AS volume, count(DISTINCT CAST(local_ts AS TIME)) AS minutes
        FROM regular GROUP BY day
        HAVING count(DISTINCT CAST(local_ts AS TIME)) / 390.0 >= 0.95
        ORDER BY day""",
        [str(source), first, last],
    ).fetchall()


def build(*, source_path: Path, coverage_path: Path, mapping_path: Path,
          output_path: Path, receipt_path: Path) -> dict[str, Any]:
    source_path, coverage_path, mapping_path = (
        path.resolve() for path in (source_path, coverage_path, mapping_path))
    if any(not path.is_file() for path in (source_path, coverage_path, mapping_path)):
        raise ValueError("canonical US500 source input missing")
    coverage, mapping = _load(coverage_path), _load(mapping_path)
    source = coverage.get("source") or {}
    span = coverage.get("selected_research_span") or {}
    if (coverage.get("decision") != "PASS_HISTORICAL_COVERAGE"
            or coverage.get("performance_accessed") is not False
            or source.get("sha256") != _sha(source_path)
            or mapping.get("decision") != "PASS_D1_SOURCE_MAPPING"
            or mapping.get("performance_accessed") is not False
            or not isinstance(span.get("first"), str)
            or not isinstance(span.get("last"), str)):
        raise ValueError("US500 coverage/mapping does not authorize canonical source")
    first, last = date.fromisoformat(span["first"]), date.fromisoformat(span["last"])
    rows = extract(source_path, first, last)
    expected = coverage.get("historical_complete_observations")
    if (not isinstance(expected, int) or expected < 500 or len(rows) != expected
            or not rows or rows[0][0] < first or rows[-1][0] > last
            or any(minutes < 371 for *_, minutes in rows)):
        raise ValueError("canonical US500 rows differ from frozen coverage")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", newline="", dir=output_path.parent,
                prefix=f".{output_path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.writer(handle, lineterminator="\n")
            for day, open_, high, low, close, volume, _ in rows:
                writer.writerow((day.strftime("%Y.%m.%d"), "00:00", open_, high,
                                 low, close, volume))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    receipt = {
        "schema_version": 1, "decision": "PASS_CANONICAL_D1_SOURCE",
        "campaign_id": "us500-d1-alquimia-v4", "symbol": "US500",
        "timeframe": "D1", "session_timezone": "America/New_York",
        "session_start": "09:30", "session_end_exclusive": "16:00",
        "minimum_session_coverage_ratio": .95,
        "first_session": rows[0][0].isoformat(),
        "last_session": rows[-1][0].isoformat(), "rows": len(rows),
        "source_path": str(source_path), "source_sha256": _sha(source_path),
        "coverage_path": str(coverage_path), "coverage_sha256": _sha(coverage_path),
        "mapping_path": str(mapping_path), "mapping_sha256": _sha(mapping_path),
        "canonical_path": str(output_path), "canonical_sha256": _sha(output_path),
        "selection_basis": "coverage_only_no_returns_or_strategy_performance",
        "performance_accessed": False, "holdout_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(receipt_path.resolve(), receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--coverage", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = build(source_path=args.source, coverage_path=args.coverage,
                   mapping_path=args.mapping, output_path=args.output,
                   receipt_path=args.receipt)
    print(json.dumps({key: result[key] for key in (
        "decision", "rows", "first_session", "last_session")}, indent=2))


if __name__ == "__main__":
    main()
