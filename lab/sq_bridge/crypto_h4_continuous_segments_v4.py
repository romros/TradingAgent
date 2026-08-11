#!/usr/bin/env python3
"""Split canonical SQ H4 CSV into lossless, independently testable segments."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


H4_SECONDS = 4 * 60 * 60


def _stamp(row: list[str]) -> datetime:
    if len(row) != 7:
        raise ValueError("canonical SQ H4 row must have seven columns")
    return datetime.strptime(f"{row[0]},{row[1]}", "%Y.%m.%d,%H:%M").replace(
        tzinfo=timezone.utc)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_continuous(*, source: Path, output_dir: Path,
                     minimum_eligible_bars: int) -> dict:
    if minimum_eligible_bars < 1:
        raise ValueError("minimum eligible bars must be positive")
    source, output_dir = source.resolve(), output_dir.resolve()
    rows: list[list[str]] = []
    stamps: list[datetime] = []
    with source.open(newline="") as handle:
        for number, row in enumerate(csv.reader(handle), 1):
            try:
                stamp = _stamp(row)
                tuple(float(value) for value in row[2:])
            except (ValueError, OverflowError) as exc:
                raise ValueError(f"invalid canonical row {number}") from exc
            if stamps and stamp <= stamps[-1]:
                raise ValueError("timestamps must be strictly increasing")
            rows.append(row); stamps.append(stamp)
    if not rows:
        raise ValueError("canonical source is empty")

    bounds = [0]
    for index in range(1, len(rows)):
        if (stamps[index] - stamps[index - 1]).total_seconds() != H4_SECONDS:
            bounds.append(index)
    bounds.append(len(rows))
    output_dir.mkdir(parents=True, exist_ok=True)
    segments = []
    for sequence, (first, end) in enumerate(zip(bounds, bounds[1:]), 1):
        path = output_dir / f"segment-{sequence:04d}.csv"
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows[first:end])
        temporary.replace(path)
        count = end - first
        segments.append({
            "sequence": sequence,
            "path": str(path),
            "sha256": _sha(path),
            "rows": count,
            "first_utc": stamps[first].isoformat(),
            "last_utc": stamps[end - 1].isoformat(),
            "eligible": count >= minimum_eligible_bars,
        })
    return {
        "schema_version": 1,
        "decision": "PASS_CONTINUOUS_SEGMENTATION",
        "source_path": str(source),
        "source_sha256": _sha(source),
        "source_rows": len(rows),
        "expected_spacing_seconds": H4_SECONDS,
        "minimum_eligible_bars": minimum_eligible_bars,
        "segment_count": len(segments),
        "eligible_segment_count": sum(item["eligible"] for item in segments),
        "all_source_rows_assigned_exactly_once": sum(item["rows"] for item in segments) == len(rows),
        "segments": segments,
        "aggregation_contract": "aggregate_trades_not_equity_curves",
        "promotion_authorized": False,
        "remaining_gate": "SQ_PER_SEGMENT_RUNTIME_AND_PYTHON_TRADE_PARITY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--minimum-eligible-bars", required=True, type=int)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    result = split_continuous(source=args.source, output_dir=args.output_dir,
                              minimum_eligible_bars=args.minimum_eligible_bars)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in
                      ("decision", "source_rows", "segment_count",
                       "eligible_segment_count")}, indent=2))


if __name__ == "__main__":
    main()

