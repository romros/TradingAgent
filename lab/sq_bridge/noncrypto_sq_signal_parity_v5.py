#!/usr/bin/env python3
"""Compile v5 signal code and compare it with the Python oracle through SQ ChartData."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab.sq_bridge.noncrypto_signal_oracle_v5 import (
    Bar, eurusd_short_trend, us500_volatility_shock_rebound,
    usdjpy_failed_break_reversion, usdjpy_session_breakout,
    xau_compression_breakout, xau_failed_shock_reversion,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "lab/sq_bridge/sq_custom_blocks_v5"
INTERNAL_ROOT = Path("/home/roman/dockers-SQ/6ACC10/internal")
OUTPUT_DIR = ROOT / "lab/sq_bridge/evidence/noncrypto_sq_signal_parity_v5"
RECEIPT = ROOT / "lab/sq_bridge/evidence/noncrypto_sq_signal_parity_v5.json"
SOURCES = (
    "SQ/Utils/AlquimiaV5Signals.java",
    "parity/AlquimiaV5ParityHarness.java",
    "parity/stubs/com/strategyquant/lib/random/MersenneTwisterRng.java",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oracle_rows() -> tuple[list[Bar], list[list[int]]]:
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    rows: list[Bar] = []
    close = 100.0
    for index in range(960):
        wave = .055 * math.sin(index / 7) + .025 * math.sin(index / 19)
        close += wave
        width = .09 + .04 * abs(math.sin(index / 11))
        if index % 137 == 0 and index > 0:
            close += 1.8 if (index // 137) % 2 else -1.8
            width = 2.1
        stamp = start + timedelta(minutes=15 * index)
        rows.append(Bar(int(stamp.timestamp() * 1000), close - wave / 2,
                        close + width, close - width, close))
    # Deterministic fixtures embedded in a longer mixed path.  These ensure the
    # parity test exercises entries, not only the overwhelmingly common WAIT.
    for index in range(304, 386):
        row = rows[index]; value = 100 + .05 * math.sin(index)
        rows[index] = Bar(row.time_ms, value, value + .5, value - .5, value)
    for index in range(386, 400):
        row = rows[index]
        rows[index] = Bar(row.time_ms, 100, 100.001, 99.999, 100)
    row = rows[400]
    rows[400] = Bar(row.time_ms, 100, 101.1, 99.99, 101)
    for index in range(580, 600):
        row = rows[index]
        rows[index] = Bar(row.time_ms, 120, 120.2, 119.8, 120)
    row = rows[600]
    rows[600] = Bar(row.time_ms, 119.5, 120.2, 117, 120.1)
    expected: list[list[int]] = []
    for at in range(len(rows)):
        expected.append([
            xau_compression_breakout(rows, at, channel_bars=8,
                                     compression_quantile=.15),
            xau_failed_shock_reversion(rows, at, shock_atr=1.5, reentry_bars=2),
            usdjpy_session_breakout(rows, at, max_range_atr_ratio=20,
                                    trend_lookback_bars=8),
            usdjpy_failed_break_reversion(rows, at, failure_window_bars=2,
                                          break_buffer_atr=.1),
            us500_volatility_shock_rebound(rows, at, shock_atr=1.5,
                                           reclaim_fraction=.7),
            eurusd_short_trend(rows, at, channel_days=10,
                               trend_lookback_days=20),
        ] if at >= 120 else [0] * 6)
    return rows, expected


def run(output_dir: Path = OUTPUT_DIR, receipt: Path = RECEIPT,
        runner=subprocess.run) -> dict:
    output_dir = output_dir.resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    oracle = output_dir / "oracle.csv"
    rows, expected = oracle_rows()
    lines = ["time_ms;open;high;low;close;xau_compression;xau_failed;usdjpy_breakout;usdjpy_failed;us500_rebound;eurusd_trend"]
    for row, signals in zip(rows, expected):
        lines.append(";".join(map(str, (row.time_ms, row.open, row.high, row.low,
                                        row.close, *signals))))
    oracle.write_text("\n".join(lines) + "\n")
    sources = [SOURCE_ROOT / member for member in SOURCES]
    library = INTERNAL_ROOT / "libs/SQTradingLib.jar"
    if not all(path.is_file() for path in sources) or not library.is_file():
        raise ValueError("SQ parity source or library missing")
    java_sources = " ".join(f"/src/{member}" for member in SOURCES)
    command = ["docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={INTERNAL_ROOT.resolve()},dst=/sq/internal,readonly",
        "--mount", f"type=bind,src={SOURCE_ROOT.resolve()},dst=/src,readonly",
        "--mount", f"type=bind,src={oracle},dst=/oracle.csv,readonly",
        "--mount", f"type=bind,src={output_dir},dst=/out",
        "eclipse-temurin:22-jdk", "sh", "-lc",
        "set -eu; rm -rf /out/classes; mkdir -p /out/classes; "
        f"javac --release 22 -cp '/sq/internal/libs/*' -d /out/classes {java_sources}; "
        "java -cp '/out/classes:/sq/internal/libs/*' alquimia.parity.AlquimiaV5ParityHarness /oracle.csv"]
    completed = runner(command, capture_output=True, text=True, timeout=300, check=False)
    if completed.returncode or "PASS_ALQUIMIA_V5_EXACT_SIGNAL_PARITY" not in completed.stdout:
        raise RuntimeError((completed.stderr + completed.stdout)[-5000:])
    coverage = {str(index): sorted(set(row[index] for row in expected[120:]))
                for index in range(6)}
    result = {
        "schema_version": 1,
        "decision": "PASS_EXACT_SQ_CHARTDATA_SIGNAL_PARITY",
        "differences": 0,
        "comparisons": (len(rows) - 120) * 6,
        "oracle_sha256": _sha(oracle),
        "source_sha256": {member: _sha(SOURCE_ROOT / member) for member in SOURCES},
        "sq_trading_lib_sha256": _sha(library),
        "network_used": False,
        "directional_coverage": coverage,
        "stdout": completed.stdout.strip(),
        "performance_accessed": False,
        "holdout_accessed": False,
        "promotion_authorized": False,
        "next_gate": "COMPILE_SIX_BUILDING_BLOCKS_AND_18_CFX_PROJECTS",
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir, args.receipt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
