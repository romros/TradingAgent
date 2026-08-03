#!/usr/bin/env python3
"""Audit a MetaTrader4 CSV after an SQ import/export round trip."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


FIELDS = ("open", "high", "low", "close", "volume")


def load(path: Path, has_header: bool, key_from: str | None = None, key_to: str | None = None) -> list[tuple[str, tuple[Decimal, ...]]]:
    rows = []
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        if has_header:
            header = next(reader, None)
            if header != ["Date", "Time", "Open", "High", "Low", "Close", "Volume"]:
                raise ValueError(f"UNEXPECTED_HEADER:{header}")
        for line, fields in enumerate(reader, 2 if has_header else 1):
            if len(fields) != 7:
                raise ValueError(f"ROW_WIDTH:{line}:{len(fields)}")
            key = f"{fields[0]}T{fields[1]}Z"
            if key_from is not None and key < key_from: continue
            if key_to is not None and key > key_to: continue
            rows.append((key, tuple(Decimal(value) for value in fields[2:])))
    return rows


def audit(source: Path, exported: Path, source_from: str | None = None, source_to: str | None = None) -> dict:
    with exported.open(newline="") as handle:
        exported_has_header = next(csv.reader(handle), []) == ["Date", "Time", "Open", "High", "Low", "Close", "Volume"]
    before, after = load(source, False, source_from, source_to), load(exported, exported_has_header)
    source_keys = [row[0] for row in before]
    export_keys = [row[0] for row in after]
    timestamps_exact = source_keys == export_keys
    compared = min(len(before), len(after))
    stats = {}
    for index, name in enumerate(FIELDS):
        errors = [abs(before[row][1][index] - after[row][1][index]) for row in range(compared)]
        stats[name] = {
            "changed_rows": sum(error != 0 for error in errors),
            "max_absolute_error": str(max(errors, default=Decimal(0))),
            "mean_absolute_error": str(sum(errors, Decimal(0)) / compared) if compared else None,
        }
    price_max = max(Decimal(stats[name]["max_absolute_error"]) for name in FIELDS[:4])
    decision = "PASS_SIGNAL_RESEARCH" if len(before) == len(after) and timestamps_exact and price_max <= Decimal("0.1") else "BLOCK"
    return {
        "schema_version": 1,
        "source_csv": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "exported_csv": str(exported),
        "exported_sha256": hashlib.sha256(exported.read_bytes()).hexdigest(),
        "exported_has_header": exported_has_header,
        "source_rows": len(before),
        "exported_rows": len(after),
        "timestamps_exact_and_ordered": timestamps_exact,
        "field_errors": stats,
        "decision": decision,
        "decision_scope": "Data integrity for signal research only; volume-dependent rules, execution, paper, and live remain unauthorized.",
        "exact_numeric_parity": all(item["changed_rows"] == 0 for item in stats.values()),
        "paper_or_live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--exported", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-from", help="Inclusive source key, for example 2026.06.01T00:00Z")
    parser.add_argument("--source-to", help="Inclusive source key, for example 2026.06.30T23:59Z")
    args = parser.parse_args()
    result = audit(args.source, args.exported, args.source_from, args.source_to)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
