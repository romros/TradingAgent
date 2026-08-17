#!/usr/bin/env python3
"""Verify SQ preserves all frozen PEP D1 dates and OHLC values."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(source: Path, exported: Path) -> dict:
    with source.open(newline="") as stream:
        left = list(csv.reader(stream))
    with exported.open(newline="") as stream:
        right = list(csv.reader(stream))
    mismatches = []
    for index, (expected, actual) in enumerate(zip(left, right)):
        if (expected[:2] != actual[:2]
                or any(abs(float(expected[column]) - float(actual[column])) > 0.0000005
                       for column in range(2, 6))):
            mismatches.append(index)
    passed = len(left) == len(right) == 1800 and not mismatches
    return {
        "schema_version": 1,
        "decision": "PASS_PEP_SQ_D1_ROUNDTRIP" if passed else "FAIL_PEP_SQ_D1_ROUNDTRIP",
        "source_rows": len(left), "export_rows": len(right),
        "date_ohlc_mismatches": len(mismatches), "source_sha256": sha(source),
        "sq_export_sha256": sha(exported), "volume_parity_required": False,
        "volume_rules_allowed": False, "performance_accessed": False,
        "holdout_2025_accessed": False, "paper_authorized": False,
        "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.source, args.export)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["decision"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
