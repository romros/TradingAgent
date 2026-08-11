"""Canonical StrategyQuant candle CSV parser shared by v4 evidence stages."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_candles(path: Path, timezone: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    expected = ["Date", "Time", "Open", "High", "Low", "Close", "Volume"]
    if list(raw.columns) != expected:
        raw = pd.read_csv(path, header=None, names=expected)
    if raw.empty:
        raise ValueError("CSV de candles buit")
    try:
        local = pd.to_datetime(
            raw["Date"].astype(str) + " " + raw["Time"].astype(str),
            format="%Y.%m.%d %H:%M", errors="raise")
        index = local.dt.tz_localize(
            timezone, ambiguous="raise", nonexistent="raise").dt.tz_convert("UTC")
        frame = pd.DataFrame({
            key.lower(): pd.to_numeric(
                raw[key], errors="raise").astype(float).to_numpy()
            for key in ("Open", "High", "Low", "Close", "Volume")
        }, index=pd.DatetimeIndex(index))
    except (TypeError, ValueError) as exc:
        raise ValueError("CSV de candles SQ invalid") from exc
    if (not frame.index.is_monotonic_increasing or frame.index.has_duplicates
            or not all((frame[key] > 0).all()
                       for key in ("open", "high", "low", "close"))
            or not (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)).all()
            or not (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)).all()):
        raise ValueError("OHLC o timestamps de candles SQ invalids")
    return frame
