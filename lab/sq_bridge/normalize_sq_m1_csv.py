#!/usr/bin/env python3
"""Audit a headerless SQ M1 export and normalize a fixed broker offset to UTC Parquet."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def normalize(source: Path, output: Path, receipt: Path, *, source_timezone: str | None = None,
              broker_utc_offset_hours: int | None = None) -> dict:
    import duckdb

    connection = duckdb.connect(":memory:")
    source_sql = str(source).replace("'", "''")
    output_sql = str(output).replace("'", "''")
    if (source_timezone is None) == (broker_utc_offset_hours is None):
        raise ValueError("Specify exactly one source timezone or fixed UTC offset")
    parsed = "strptime(column0 || ' ' || column1, '%Y.%m.%d %H:%M')"
    if source_timezone:
        if source_timezone != "America/New_York":
            raise ValueError("Only America/New_York is supported without optional timezone dependencies")
        year = f"year({parsed})"
        march_anchor = f"make_date({year}, 3, 8)"
        november_anchor = f"make_date({year}, 11, 1)"
        dst_start = f"({march_anchor} + ((7-dayofweek({march_anchor}))%7)*INTERVAL '1 day' + INTERVAL '2 hours')"
        dst_end = f"({november_anchor} + ((7-dayofweek({november_anchor}))%7)*INTERVAL '1 day' + INTERVAL '2 hours')"
        timestamp_sql = (f"CASE WHEN {year} < 2007 THEN error('US DST normalization requires year >= 2007') "
                         f"WHEN {parsed} >= {dst_start} AND {parsed} < {dst_end} "
                         f"THEN {parsed} + INTERVAL '4 hours' ELSE {parsed} + INTERVAL '5 hours' END")
        normalization = "America/New_York local => UTC using US DST rules effective 2007"
    else:
        offset = -int(broker_utc_offset_hours)
        timestamp_sql = f"{parsed} + INTERVAL '{offset} hours'"
        normalization = f"timestamp + {offset} hours => UTC"
    relation = f"""SELECT
      CAST(epoch({timestamp_sql}) AS BIGINT) AS ts,
      CAST(column2 AS DOUBLE) AS open, CAST(column3 AS DOUBLE) AS high,
      CAST(column4 AS DOUBLE) AS low, CAST(column5 AS DOUBLE) AS close,
      CAST(column6 AS DOUBLE) AS volume
      FROM read_csv('{source_sql}', header=false, all_varchar=true)"""
    metrics = connection.execute(f"""WITH source AS ({relation}), ordered AS (
      SELECT *, lag(ts) OVER (ORDER BY ts) AS previous_ts FROM source)
      SELECT count(*) AS row_count, min(ts) AS first_ts, max(ts) AS last_ts,
        count(*)-count(DISTINCT ts) duplicate_timestamps,
        count(*) FILTER (WHERE high < greatest(open,close) OR low > least(open,close) OR low > high) invalid_ohlc,
        count(*) FILTER (WHERE previous_ts IS NOT NULL AND ts-previous_ts > 60) gaps,
        max((ts-previous_ts)/60) max_gap_minutes
      FROM ordered""").fetchone()
    output.parent.mkdir(parents=True, exist_ok=True)
    connection.execute(f"COPY ({relation} ORDER BY ts) TO '{output_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    result = {
        "schema_version": 1, "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "output": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "source_timezone": source_timezone, "broker_utc_offset_hours": broker_utc_offset_hours,
        "normalization": normalization,
        "rows": metrics[0],
        "first_ts_utc": datetime.fromtimestamp(metrics[1], timezone.utc).isoformat(),
        "last_ts_utc": datetime.fromtimestamp(metrics[2], timezone.utc).isoformat(),
        "duplicate_timestamps": metrics[3], "invalid_ohlc": metrics[4],
        "gaps_over_one_minute": metrics[5], "max_gap_minutes": metrics[6],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--broker-utc-offset-hours", type=int)
    parser.add_argument("--source-timezone")
    args = parser.parse_args()
    print(json.dumps(normalize(args.source, args.output, args.receipt,
                               source_timezone=args.source_timezone,
                               broker_utc_offset_hours=args.broker_utc_offset_hours), indent=2))


if __name__ == "__main__":
    main()
