#!/usr/bin/env python3
"""Build an SQ Indicator Tester file from canonical H4 OHLC and Python ATR."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from lab.sq_bridge.crypto_h4_gap_safe_atr_v4 import gap_safe_sma_atr


def build(*, source: Path, output: Path, maximum_rows: int = 512) -> dict:
    if maximum_rows < 15:
        raise ValueError("oracle needs at least 15 rows")
    rows = []
    with source.resolve().open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) != 7:
                raise ValueError("canonical row must have seven columns")
            rows.append(row)
            if len(rows) == maximum_rows:
                break
    if len(rows) < 15:
        raise ValueError("canonical source too short")
    stamps = [datetime.strptime(f"{row[0]} {row[1]}", "%Y.%m.%d %H:%M").replace(
        tzinfo=timezone.utc) for row in rows]
    highs = [float(row[3]) for row in rows]
    lows = [float(row[4]) for row in rows]
    closes = [float(row[5]) for row in rows]
    atr = gap_safe_sma_atr(
        [int(stamp.timestamp() * 1000) for stamp in stamps], highs, lows, closes)
    output = output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        for row, stamp, value in zip(rows, stamps, atr):
            encoded = "NaN" if math.isnan(value) else repr(value)
            writer.writerow([stamp.strftime("%Y.%m.%d %H:%M:%S"), *row[2:6],
                             row[6], encoded])
    return {
        "schema_version": 1,
        "decision": "PASS_SQ_INDICATOR_ORACLE_BUILT",
        "source_path": str(source.resolve()),
        "source_sha256": hashlib.sha256(source.resolve().read_bytes()).hexdigest(),
        "output_path": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "rows": len(rows),
        "period": 14,
        "sq_bars_to_reserve": 14,
        "comparison_decimals": 10,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maximum-rows", type=int, default=512)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = build(source=args.source, output=args.output,
                   maximum_rows=args.maximum_rows)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
