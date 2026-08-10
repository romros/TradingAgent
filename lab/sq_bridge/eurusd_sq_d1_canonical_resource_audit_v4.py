#!/usr/bin/env python3
"""Audit the canonical EURUSD NY17 D1 source after an SQCLI round trip."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, tuple[tuple[float, ...], int]]:
    result = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 7:
                continue
            day = row[0]
            if day in result:
                raise ValueError(f"duplicate day: {day}")
            result[day] = (tuple(float(value) for value in row[2:6]), int(row[6]))
    if not result:
        raise ValueError("empty D1 CSV")
    return result


def audit(source_path: Path, export_path: Path, source_receipt: dict) -> dict:
    source, exported = read(source_path), read(export_path)
    source_days, export_days = set(source), set(exported)
    common = sorted(source_days & export_days)
    price_deltas = [max(abs(a - b) for a, b in zip(source[day][0], exported[day][0]))
                    for day in common]
    volume_changes = [{"day": day, "source": source[day][1],
                       "sq_export": exported[day][1]}
                      for day in common if source[day][1] != exported[day][1]]
    accepted_volume_changes = all(row["source"] == 0 and row["sq_export"] == 1
                                  for row in volume_changes)
    expected_rows = source_receipt.get("rows")
    checks = {
        "source_receipt_pass": source_receipt.get("decision") == "PASS_CANONICAL_D1_IMPORT_SOURCE",
        "source_hash_matches_receipt": sha256(source_path)
            == (source_receipt.get("output") or {}).get("sha256"),
        "expected_row_count": len(source) == len(exported) == expected_rows == 5884,
        "identical_dates": source_days == export_days,
        "exact_ohlc_roundtrip": len(common) == len(source) and max(price_deltas, default=1) == 0,
        "only_zero_volume_normalized": accepted_volume_changes,
    }
    passed = all(checks.values())
    return {
        "schema_version": 1, "symbol": "EURUSD_ALQ_NY17_D1", "instrument": "EURUSD",
        "timeframe": "D1", "session_timezone": "America/New_York",
        "session_boundary": "17:00", "sq_version": "143.2708",
        "performance_accessed": False, "sq_rows": len(exported),
        "source_rows": len(source), "common_rows": len(common),
        "ohlc_match_ratio": (sum(delta == 0 for delta in price_deltas) / len(common)
                             if common else 0),
        "maximum_ohlc_delta": max(price_deltas, default=None),
        "sunday_fragment_bars": 0,
        "volume_normalizations": volume_changes,
        "checks": checks,
        "source_csv": {"path": str(source_path), "bytes": source_path.stat().st_size,
                       "sha256": sha256(source_path)},
        "sq_export": {"path": str(export_path), "bytes": export_path.stat().st_size,
                      "sha256": sha256(export_path)},
        "decision": "PASS_SQ_D1_RESOURCE" if passed else "BLOCK_SQ_D1_RESOURCE_PARITY",
        "research_authorized": passed, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--sq-export", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.source_receipt.read_text())
    result = audit(args.source, args.sq_export, receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"]}, indent=2))


if __name__ == "__main__":
    main()
