#!/usr/bin/env python3
"""Build deterministic Python signal expectations for the SQ H4 harness."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from lab.sq_bridge.crypto_h4_train_engine_v4 import Bars, signals


CASES = ((12, 1, 0.0), (12, 2, 3.5), (24, 1, 3.5),
         (24, 2, 10.0), (55, 1, 0.0), (55, 2, 10.0))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bars(path: Path, maximum_rows: int) -> Bars:
    stamps, columns = [], [[], [], [], []]
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) != 7: raise ValueError("canonical row must have seven columns")
            stamps.append(datetime.strptime(f"{row[0]} {row[1]}", "%Y.%m.%d %H:%M").replace(
                tzinfo=timezone.utc))
            for target, value in zip(columns, row[2:6]): target.append(float(value))
            if len(stamps) == maximum_rows: break
    if len(stamps) < 57: raise ValueError("signal oracle source too short")
    segment = np.zeros(len(stamps), dtype=np.int64)
    current = 0
    for index in range(1, len(stamps)):
        if (stamps[index] - stamps[index - 1]).total_seconds() != 14_400:
            current += 1
        segment[index] = current
    return Bars(tuple(stamps), *(np.asarray(values, dtype=float) for values in columns), segment)


def build(*, source: Path, output: Path, maximum_rows: int = 512) -> dict:
    source, output = source.resolve(), output.resolve()
    bars = _bars(source, maximum_rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        writer.writerow(("decision", "period", "shift", "level", "momentum_above",
                         "momentum_below", "channel_above", "channel_below"))
        for period, shift, level in CASES:
            momentum_up, momentum_down, _ = signals(bars, "time_series_momentum", "both", {
                "indicator_period": period, "shift": shift, "roc_threshold_pct": level})
            channel_up, channel_down, _ = signals(bars, "channel_breakout", "both", {
                "indicator_period": period, "shift": shift})
            for decision in range(len(bars) - 1):
                writer.writerow((decision, period, shift, level,
                                 int(momentum_up[decision]), int(momentum_down[decision]),
                                 int(channel_up[decision]), int(channel_down[decision])))
                count += 1
    return {"schema_version": 1, "decision": "PASS_PYTHON_SIGNAL_ORACLE_BUILT",
            "source_path": str(source), "source_sha256": _sha(source),
            "output_path": str(output), "output_sha256": _sha(output),
            "source_rows": len(bars), "cases": [list(case) for case in CASES],
            "expectations": count, "evaluation_timing": "entry_bar_with_sq_shift_1_or_2"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maximum-rows", type=int, default=512)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = build(source=args.source, output=args.output, maximum_rows=args.maximum_rows)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
