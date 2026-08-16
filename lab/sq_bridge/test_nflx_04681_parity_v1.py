import pytest

from lab.sq_bridge.nflx_04681_parity_v1 import atr


def test_atr_uses_progressive_seed_then_wilder_smoothing():
    values = [2.0, 4.0, 8.0, 10.0]
    assert atr(values, 3) == pytest.approx(
        [2.0, 3.0, 14.0 / 3.0, 58.0 / 9.0])


def test_long_period_has_value_before_full_window():
    assert atr([2.0, 4.0], 104) == [2.0, 3.0]
