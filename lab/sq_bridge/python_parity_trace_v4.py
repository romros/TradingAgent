#!/usr/bin/env python3
"""Execute a canonical Alquimia IR into a reproducible Python parity trace."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.strategy_ir_runtime import simulate_trade_trace


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_mt4_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, header=None, names=(
        "date", "time", "open", "high", "low", "close", "volume"))
    if frame.empty:
        raise ValueError("CSV de paritat buit")
    index = pd.to_datetime(
        frame.pop("date") + " " + frame.pop("time"),
        format="%Y.%m.%d %H:%M", utc=True, errors="raise")
    frame.index = index
    return frame[["open", "high", "low", "close"]].astype(float)


def _utc_bound(value: str | None) -> pd.Timestamp | None:
    if value is None:
        return None
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        result = result.tz_localize("UTC")
    else:
        result = result.tz_convert("UTC")
    return result


def build(ir_path: Path, market_data_path: Path, notional_usdc: float,
          output_path: Path, evaluation_start: str | None = None,
          evaluation_end: str | None = None) -> dict:
    ir = json.loads(ir_path.read_text())
    trace = simulate_trade_trace(
        ir, load_mt4_csv(market_data_path), notional_usdc,
        evaluation_start=_utc_bound(evaluation_start),
        evaluation_end=_utc_bound(evaluation_end))
    trace.update({
        "canonical_ir_path": str(ir_path.resolve()),
        "canonical_ir_sha256": sha256(ir_path),
        "market_data_path": str(market_data_path.resolve()),
        "market_data_sha256": sha256(market_data_path),
    })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ir", type=Path, required=True)
    parser.add_argument("--market-data", type=Path, required=True)
    parser.add_argument("--notional-usdc", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluation-start")
    parser.add_argument("--evaluation-end")
    args = parser.parse_args()
    result = build(args.ir, args.market_data, args.notional_usdc, args.output,
                   args.evaluation_start, args.evaluation_end)
    print(json.dumps({"candidate_id": result["candidate_id"],
                      "signals": len(result["signals"]),
                      "trades": len(result["trades"])}, indent=2))


if __name__ == "__main__":
    main()
