#!/usr/bin/env python3
"""Verify native SQ retest entry parity for the frozen MSFT capitulation rule."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

from three_strategy_portfolio_v1 import load_msft, signals


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(candles: Path, orders: Path) -> dict:
    rows = load_msft(candles)
    expected = [
        rows[i]["date"] for i in signals(rows)
        if dt.date(2003, 1, 2) <= rows[i]["date"] <= dt.date(2024, 12, 31)
    ]
    with orders.open(newline="") as handle:
        actual_rows = list(csv.DictReader(handle, delimiter=";"))
    actual = [
        dt.datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S").date()
        for row in actual_rows
    ]
    exact = expected == actual
    return {
        "schema_version": 1,
        "strategy": "MSFT_CAPITULATION_D1_NATIVE_V1",
        "period": {"from": "2003-01-02", "to": "2024-12-31"},
        "expected_python_entries": len(expected),
        "actual_sq_entries": len(actual),
        "entry_dates_exact_match": exact,
        "missing_in_sq": [str(day) for day in expected if day not in actual],
        "extra_in_sq": [str(day) for day in actual if day not in expected],
        "decision": "PASS_EXACT_SIGNAL_PARITY" if exact else "REJECT_SIGNAL_PARITY",
        "price_comparison_scope": "Not asserted: Python source is adjusted while the native SQ resource is split-consistent nominal OHLC.",
        "candles_sha256": digest(candles),
        "orders_sha256": digest(orders),
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles", type=Path, required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(args.candles, args.orders)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["entry_dates_exact_match"] else 1)


if __name__ == "__main__":
    main()
