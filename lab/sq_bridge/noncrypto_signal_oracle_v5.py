#!/usr/bin/env python3
"""Performance-blind canonical price-signal oracle for Alquimia v5.

Rows are chronological.  Every function evaluates only the current and older
completed bars and returns -1 (short), 0 (wait), or 1 (long).  Entry is always
the next bar open and is deliberately outside this signal layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Sequence


@dataclass(frozen=True)
class Bar:
    time_ms: int
    open: float
    high: float
    low: float
    close: float


def _true_range(rows: Sequence[Bar], at: int) -> float:
    if at <= 0:
        return rows[at].high - rows[at].low
    previous = rows[at - 1].close
    return max(rows[at].high - rows[at].low,
               abs(rows[at].high - previous), abs(rows[at].low - previous))


def atr(rows: Sequence[Bar], at: int, period: int = 14) -> float:
    if period < 1 or at < period:
        return float("nan")
    value = sum(_true_range(rows, index) for index in range(at - period + 1, at + 1)) / period
    return value if value > 0 and isfinite(value) else float("nan")


def _quantile(values: Sequence[float], fraction: float) -> float:
    if not values or not 0 <= fraction <= 1:
        return float("nan")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def xau_compression_breakout(rows: Sequence[Bar], at: int, *, channel_bars: int,
                             compression_quantile: float) -> int:
    """Break prior channel while prior bar's normalized ATR was compressed.

    Compression uses 96 completed M15 observations (one trading day) ending on
    the bar before the breakout.  The breakout bar itself cannot manufacture
    its own compression condition.
    """
    compression_lookback = 96
    start = at - 1 - compression_lookback + 1
    if channel_bars < 2 or start < 14:
        return 0
    normalized = []
    for index in range(start, at):
        value = atr(rows, index)
        if not isfinite(value) or rows[index].close <= 0:
            return 0
        normalized.append(value / rows[index].close)
    previous_normalized = normalized[-1]
    # Compare the last completed state against earlier states, not itself.
    if previous_normalized > _quantile(normalized[:-1], compression_quantile):
        return 0
    prior = rows[at - channel_bars:at]
    if rows[at].close > max(row.high for row in prior):
        return 1
    if rows[at].close < min(row.low for row in prior):
        return -1
    return 0


def xau_failed_shock_reversion(rows: Sequence[Bar], at: int, *, shock_atr: float,
                               reentry_bars: int) -> int:
    """Fade the newest qualifying shock that closes back through its open."""
    if shock_atr <= 0 or reentry_bars < 1:
        return 0
    for shock in range(at - 1, max(13, at - reentry_bars) - 1, -1):
        value = atr(rows, shock - 1)
        if not isfinite(value):
            continue
        displacement = rows[shock].close - rows[shock - 1].close
        if displacement >= shock_atr * value and rows[at].close < rows[shock].open:
            return -1
        if displacement <= -shock_atr * value and rows[at].close > rows[shock].open:
            return 1
    return 0


def _utc(row: Bar) -> datetime:
    return datetime.fromtimestamp(row.time_ms / 1000, tz=timezone.utc)


def _same_utc_day(left: Bar, right: Bar) -> bool:
    return _utc(left).date() == _utc(right).date()


def _asia_range(rows: Sequence[Bar], at: int) -> tuple[float, float] | None:
    day = _utc(rows[at]).date()
    asia = [row for row in rows[:at] if _utc(row).date() == day and 0 <= _utc(row).hour < 7]
    # M15, 00:00 through 06:45 UTC: exactly 28 completed bars.
    if len(asia) != 28:
        return None
    return max(row.high for row in asia), min(row.low for row in asia)


def usdjpy_session_breakout(rows: Sequence[Bar], at: int, *, max_range_atr_ratio: float,
                            trend_lookback_bars: int) -> int:
    """Break the completed 00:00–06:45 UTC range during 07:00–11:45 UTC."""
    now = _utc(rows[at])
    if not 7 <= now.hour < 12 or trend_lookback_bars < 2:
        return 0
    bounds = _asia_range(rows, at)
    value = atr(rows, at - 1)
    if bounds is None or not isfinite(value) or bounds[0] - bounds[1] > max_range_atr_ratio * value:
        return 0
    previous = at - trend_lookback_bars
    if previous < 0 or not _same_utc_day(rows[previous], rows[at]):
        return 0
    trend = rows[at - 1].close - rows[previous].close
    if rows[at].close > bounds[0] and trend > 0:
        return 1
    if rows[at].close < bounds[1] and trend < 0:
        return -1
    return 0


def usdjpy_failed_break_reversion(rows: Sequence[Bar], at: int, *,
                                  failure_window_bars: int,
                                  break_buffer_atr: float) -> int:
    """Fade an Asian-range break that closes back inside during London hours."""
    now = _utc(rows[at])
    if not 7 <= now.hour < 12 or failure_window_bars < 1 or break_buffer_atr < 0:
        return 0
    bounds = _asia_range(rows, at)
    value = atr(rows, at - 1)
    if bounds is None or not isfinite(value) or not bounds[1] < rows[at].close < bounds[0]:
        return 0
    for index in range(max(0, at - failure_window_bars), at):
        if not _same_utc_day(rows[index], rows[at]):
            continue
        if rows[index].high > bounds[0] + break_buffer_atr * value:
            return -1
        if rows[index].low < bounds[1] - break_buffer_atr * value:
            return 1
    return 0


def us500_volatility_shock_rebound(rows: Sequence[Bar], at: int, *, shock_atr: float,
                                   reclaim_fraction: float) -> int:
    """Long-only daily selloff whose close reclaims a fraction of its range."""
    if at < 20 or shock_atr <= 0 or not 0 <= reclaim_fraction <= 1:
        return 0
    value = atr(rows, at - 1)
    row = rows[at]
    if not isfinite(value) or rows[at - 1].close - row.low < shock_atr * value:
        return 0
    bar_range = row.high - row.low
    if bar_range <= 0 or row.close < row.low + reclaim_fraction * bar_range:
        return 0
    # Point-in-time volatility veto: prior 5-day TR cannot exceed prior 20-day TR average.
    fast = sum(_true_range(rows, i) for i in range(at - 5, at)) / 5
    slow = sum(_true_range(rows, i) for i in range(at - 20, at)) / 20
    return 1 if fast <= slow else 0


def eurusd_short_trend(rows: Sequence[Bar], at: int, *, channel_days: int,
                       trend_lookback_days: int) -> int:
    """Daily prior-channel breakout aligned with a lagged close return."""
    required = max(channel_days, trend_lookback_days)
    if channel_days < 2 or trend_lookback_days < 2 or at < required:
        return 0
    prior = rows[at - channel_days:at]
    trend = rows[at - 1].close - rows[at - trend_lookback_days].close
    if rows[at].close > max(row.high for row in prior) and trend > 0:
        return 1
    if rows[at].close < min(row.low for row in prior) and trend < 0:
        return -1
    return 0
