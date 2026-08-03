#!/usr/bin/env python3
"""Read-only integrity/coverage audit for native Ostium recorder CSVs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def load_csv_tree(root: Path) -> pd.DataFrame:
    files = sorted(path for path in root.rglob("*.csv") if not path.name.startswith("."))
    if not files:
        return pd.DataFrame(columns=COLUMNS)
    frames = [pd.read_csv(path, names=COLUMNS) for path in files]
    frame = pd.concat(frames, ignore_index=True)
    frame["utc"] = pd.to_datetime(frame.timestamp, unit="s", utc=True)
    return frame.sort_values(["timestamp"], kind="stable").reset_index(drop=True)


def audit_symbol(symbol: str, root: Path, kind: str, maximum_one_minute_return_pct: float = 5.0) -> dict:
    frame = load_csv_tree(root)
    if frame.empty:
        return {"symbol": symbol, "decision": "BLOCK_NO_NATIVE_CANDLES", "rows": 0, "root": str(root)}
    duplicates = int(frame.timestamp.duplicated().sum())
    finite = np.isfinite(frame[["open", "high", "low", "close"]]).all(axis=1)
    ohlc_ok = ((frame.low <= frame[["open", "close"]].min(axis=1))
               & (frame.high >= frame[["open", "close"]].max(axis=1))
               & (frame.low <= frame.high) & (frame[["open", "high", "low", "close"]] > 0).all(axis=1))
    returns = frame.close.pct_change().abs() * 100
    # Overnight/session gaps are economically possible; flag only consecutive-minute jumps.
    minute_delta = frame.timestamp.diff()
    continuous_returns = returns.where(minute_delta == 60)
    outlier_mask = continuous_returns > maximum_one_minute_return_pct
    outliers = []
    for at in np.flatnonzero(outlier_mask.to_numpy()):
        outliers.append({"utc": frame.utc.iloc[at].isoformat(), "previous_close": float(frame.close.iloc[at - 1]),
                         "close": float(frame.close.iloc[at]), "absolute_return_pct": float(returns.iloc[at])})
    unique_days = int(frame.utc.dt.date.nunique())
    span_days = int((frame.utc.max() - frame.utc.min()).total_seconds() // 86400)
    gaps_over_5m = int(((minute_delta > 300) & (frame.utc.dt.date == frame.utc.shift().dt.date)).sum())
    outside_rth = None
    if kind == "us_equity":
        local = frame.utc.dt.tz_convert("America/New_York")
        minutes = local.dt.hour * 60 + local.dt.minute
        outside_rth = int((~((minutes >= 570) & (minutes <= 960) & (local.dt.dayofweek < 5))).sum())
    enough_coverage = span_days >= 60 and unique_days >= 40
    integrity_ok = duplicates == 0 and bool(finite.all()) and bool(ohlc_ok.all()) and not outliers
    decision = "PASS_NATIVE_PARITY_SAMPLE" if enough_coverage and integrity_ok else "BLOCK_NATIVE_INTEGRITY_OR_COVERAGE"
    return {"symbol": symbol, "kind": kind, "root": str(root), "rows": len(frame),
            "first_utc": frame.utc.min().isoformat(), "last_utc": frame.utc.max().isoformat(),
            "calendar_span_days": span_days, "unique_utc_days": unique_days,
            "duplicate_timestamps": duplicates, "nonfinite_ohlc_rows": int((~finite).sum()),
            "invalid_ohlc_rows": int((~ohlc_ok).sum()), "within_day_gaps_over_5m": gaps_over_5m,
            "outside_us_rth_rows": outside_rth, "maximum_continuous_minute_return_pct": float(continuous_returns.max()),
            "outlier_threshold_pct": maximum_one_minute_return_pct, "continuous_return_outliers": outliers,
            "zero_volume_rows": int((frame.volume == 0).sum()), "enough_coverage_for_parity": enough_coverage,
            "integrity_ok": integrity_ok, "decision": decision,
            "performance_research_authorized": False, "paper_or_live_authorized": False}


def run(specs: list[tuple[str, Path, str]]) -> dict:
    symbols = [audit_symbol(*spec) for spec in specs]
    return {"schema_version": 1, "audit_id": "ostium-native-coverage-2026-08-03",
            "purpose": "data integrity and parity sample only; no strategy performance",
            "symbols": symbols,
            "native_parity_ready_symbols": [item["symbol"] for item in symbols if item["decision"] == "PASS_NATIVE_PARITY_SAMPLE"],
            "performance_metrics_accessed": False, "global_holdout_accessed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candles-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    specs = [("MSFT", args.candles_root / "MSFT", "us_equity"),
             ("NVDAUSD", args.candles_root / "NVDAUSD", "us_equity"),
             ("NDXUSD", args.candles_root / "NDXUSD", "index")]
    result = run(specs)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({item["symbol"]: {key: item[key] for key in ("decision", "rows", "calendar_span_days",
                      "unique_utc_days", "duplicate_timestamps", "invalid_ohlc_rows",
                      "maximum_continuous_minute_return_pct", "continuous_return_outliers")}
                      for item in result["symbols"]}, indent=2))


if __name__ == "__main__":
    main()
