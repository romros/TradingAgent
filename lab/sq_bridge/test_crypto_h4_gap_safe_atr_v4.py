from datetime import datetime, timedelta, timezone
import math

import numpy as np
import pytest

from lab.sq_bridge.crypto_h4_gap_safe_atr_v4 import (
    H4_MILLISECONDS, gap_safe_sma_atr,
)
from lab.sq_bridge.crypto_h4_train_engine_v4 import Bars, true_range_and_atr


def test_oracle_matches_canonical_train_engine_across_gap():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    offsets = list(range(17)) + list(range(18, 36))
    stamps = tuple(start + timedelta(hours=4 * offset) for offset in offsets)
    close = np.asarray([100 + (index % 7) for index in range(len(stamps))], dtype=float)
    high, low = close + 2 + np.arange(len(close)) % 3, close - 1
    open_ = close.copy()
    segment = np.asarray([0] * 17 + [1] * 18, dtype=np.int64)
    bars = Bars(stamps, open_, high, low, close, segment)

    expected = true_range_and_atr(bars)[1]
    actual = gap_safe_sma_atr(
        [int(stamp.timestamp() * 1000) for stamp in stamps], high, low, close)
    np.testing.assert_allclose(actual, expected, equal_nan=True)
    assert math.isnan(actual[17])
    assert math.isfinite(actual[30])


def test_exact_h4_spacing_is_part_of_contract():
    times = [0, H4_MILLISECONDS, 2 * H4_MILLISECONDS + 1]
    actual = gap_safe_sma_atr(times, [2, 3, 4], [1, 2, 3], [1.5, 2.5, 3.5], 2)
    assert actual[1] == pytest.approx(1.25)
    assert math.isnan(actual[2])


def test_bad_inputs_fail_closed():
    with pytest.raises(ValueError, match="strictly increasing"):
        gap_safe_sma_atr([0, 0], [2, 2], [1, 1], [1.5, 1.5], 2)

