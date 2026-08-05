#!/usr/bin/env python3
"""Create an auditable Forex quarantine pilot from Ostium M1 parquet."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from lab.sq_bridge.intraday_source_parity import load_ohlcv_parquet
from lab.sq_bridge.ostium_fx_quarantine import (
    detect_roll_window_anomalies, exclude_quarantined_dates, exclude_utc_buckets,
    quarantined_local_dates, quarantined_utc_buckets,
)


def load_input(path: Path) -> list[dict]:
    if path.suffix.lower() == ".parquet":
        return load_ohlcv_parquet([path])
    if path.suffix.lower() != ".csv":
        raise ValueError(f"UNSUPPORTED_INPUT_FORMAT:{path.suffix}")
    rows = []
    with path.open(newline="") as handle:
        for line, values in enumerate(csv.reader(handle), start=1):
            if len(values) != 6:
                raise ValueError(f"INVALID_CSV_COLUMNS:{line}")
            ts, open_, high, low, close, volume = values
            rows.append({"ts": int(ts), "open": float(open_), "high": float(high),
                         "low": float(low), "close": float(close), "volume": float(volume)})
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--threshold-bps", type=float, default=8.0)
    parser.add_argument(
        "--quarantine-bucket-minutes", type=int,
        help="Exclude only UTC buckets at this research timeframe instead of whole local dates",
    )
    args = parser.parse_args()

    rows = load_input(args.input)
    receipts = detect_roll_window_anomalies(rows, threshold_bps=args.threshold_bps)
    dates = quarantined_local_dates(receipts)
    buckets = None
    if args.quarantine_bucket_minutes:
        buckets = quarantined_utc_buckets(receipts, args.quarantine_bucket_minutes)
        kept = exclude_utc_buckets(rows, buckets, args.quarantine_bucket_minutes)
        action = "EXCLUDE_INTERSECTING_UTC_BUCKET_NO_PRICE_CORRECTION"
    else:
        kept = exclude_quarantined_dates(rows, dates)
        action = "EXCLUDE_WHOLE_LOCAL_DATE_NO_PRICE_CORRECTION"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(":memory:")
    connection.execute(
        "CREATE TABLE kept(ts BIGINT, open DOUBLE, high DOUBLE, low DOUBLE, "
        "close DOUBLE, volume DOUBLE)"
    )
    connection.executemany(
        "INSERT INTO kept VALUES (?, ?, ?, ?, ?, ?)",
        [(r["ts"], r["open"], r["high"], r["low"], r["close"], r["volume"]) for r in kept],
    )
    connection.execute("COPY kept TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(args.output)])
    result = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": args.symbol.upper(),
        "policy": {
            "detector": "NY_ROLL_WINDOW_CLOSE_JUMP",
            "window_new_york": "16:55-17:35",
            "threshold_bps_strictly_greater_than": args.threshold_bps,
            "action": action,
            "quarantine_bucket_minutes": args.quarantine_bucket_minutes,
            "reference_market_used_for_detection": False,
        },
        "input": {"path": str(args.input), "sha256": _sha256(args.input), "rows": len(rows)},
        "output": {"path": str(args.output), "sha256": _sha256(args.output), "rows": len(kept)},
        "quarantined_local_dates": sorted(dates),
        "quarantined_utc_bucket_starts": sorted(buckets) if buckets is not None else None,
        "quarantined_rows": len(rows) - len(kept),
        "receipts": receipts,
        "scope": "DATA_QUALITY_PILOT_NOT_RESEARCH_PAPER_OR_LIVE_AUTHORIZATION",
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
