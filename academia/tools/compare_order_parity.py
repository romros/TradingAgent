#!/usr/bin/env python3
"""Quantify order parity between StrategyQuant and a target engine CSV."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


ALIASES = {
    "side": ("Type", "side", "type", "direction"),
    "open_time": ("Open time", "open_time", "entry_time"),
    "close_time": ("Close time", "close_time", "exit_time"),
    "open_price": ("Open price", "open_price", "entry_price"),
    "close_price": ("Close price", "close_price", "exit_price"),
    "size": ("Size", "size", "quantity", "qty"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(sample[:4096], delimiters=",;\t")
    return list(csv.DictReader(sample.splitlines(), dialect=dialect))


def value(row: dict[str, str], field: str) -> str:
    for alias in ALIASES[field]:
        if alias in row and row[alias] != "":
            return row[alias]
    raise KeyError(f"missing {field}; accepted headers: {ALIASES[field]}")


def number(raw: str) -> float:
    return float(raw.replace(" ", "").replace(",", "."))


def timestamp(raw: str) -> datetime:
    for fmt in ("%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    raise ValueError(f"unsupported timestamp: {raw}")


def compare(sq_rows: list[dict[str, str]], target_rows: list[dict[str, str]], time_tolerance: float, price_tolerance: float, size_tolerance: float) -> dict:
    mismatches = []
    for index, (sq, target) in enumerate(zip(sq_rows, target_rows), 1):
        row_errors = []
        if value(sq, "side").lower() != value(target, "side").lower():
            row_errors.append("side")
        for field in ("open_time", "close_time"):
            if abs((timestamp(value(sq, field)) - timestamp(value(target, field))).total_seconds()) > time_tolerance:
                row_errors.append(field)
        for field, tolerance in (("open_price", price_tolerance), ("close_price", price_tolerance), ("size", size_tolerance)):
            if abs(number(value(sq, field)) - number(value(target, field))) > tolerance:
                row_errors.append(field)
        if row_errors:
            mismatches.append({"row": index, "fields": row_errors})
    count_delta = len(target_rows) - len(sq_rows)
    passed = count_delta == 0 and not mismatches
    return {
        "passed": passed,
        "decision": "PARITY_PASS" if passed else "PARITY_FAIL",
        "sq_orders": len(sq_rows),
        "target_orders": len(target_rows),
        "count_delta": count_delta,
        "mismatched_orders": len(mismatches),
        "mismatches": mismatches[:100],
        "tolerances": {"time_seconds": time_tolerance, "price": price_tolerance, "size": size_tolerance},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sq_csv", type=Path)
    parser.add_argument("target_csv", type=Path)
    parser.add_argument("--time-tolerance-seconds", type=float, default=0)
    parser.add_argument("--price-tolerance", type=float, default=0)
    parser.add_argument("--size-tolerance", type=float, default=0)
    args = parser.parse_args()
    result = compare(read_csv(args.sq_csv), read_csv(args.target_csv), args.time_tolerance_seconds, args.price_tolerance, args.size_tolerance)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
