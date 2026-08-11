#!/usr/bin/env python3
"""Executable oracle for the Alquimia H4 gap-safe SMA ATR contract."""
from __future__ import annotations

from collections.abc import Sequence
import math


H4_MILLISECONDS = 4 * 60 * 60 * 1000


def gap_safe_sma_atr(
    times_ms: Sequence[int],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
    expected_spacing_ms: int = H4_MILLISECONDS,
) -> list[float]:
    """Return the canonical ATR, resetting true range at every data gap.

    An ATR is defined only after ``period`` consecutive bars.  The first true
    range after a gap is high-low; later ranges may use the previous close.
    This mirrors ``crypto_h4_train_engine_v4.true_range_and_atr`` exactly.
    """
    size = len(times_ms)
    if period < 1 or expected_spacing_ms < 1:
        raise ValueError("period and spacing must be positive")
    if any(len(values) != size for values in (highs, lows, closes)):
        raise ValueError("OHLC and timestamp lengths differ")
    if any(times_ms[index] <= times_ms[index - 1] for index in range(1, size)):
        raise ValueError("timestamps must be strictly increasing")

    ranges: list[float] = []
    segments: list[int] = []
    segment = 0
    for index in range(size):
        values = (float(highs[index]), float(lows[index]), float(closes[index]))
        if not all(math.isfinite(value) for value in values) or values[0] < values[1]:
            raise ValueError("invalid HLC value")
        continuous = (index > 0 and
                      times_ms[index] - times_ms[index - 1] == expected_spacing_ms)
        if index and not continuous:
            segment += 1
        segments.append(segment)
        ranges.append(max(values[0] - values[1],
                          abs(values[0] - float(closes[index - 1])),
                          abs(values[1] - float(closes[index - 1])))
                      if continuous else values[0] - values[1])

    result = [math.nan] * size
    for index in range(period - 1, size):
        first = index - period + 1
        if segments[first] == segments[index]:
            result[index] = math.fsum(ranges[first:index + 1]) / period
    return result

