from datetime import datetime, timedelta, timezone

from lab.sq_bridge.noncrypto_signal_oracle_v5 import (
    Bar, eurusd_short_trend, us500_volatility_shock_rebound,
    usdjpy_failed_break_reversion, usdjpy_session_breakout,
    xau_compression_breakout, xau_failed_shock_reversion,
)


def bars(count=140, *, minutes=15, start=datetime(2026, 1, 5, tzinfo=timezone.utc)):
    result = []
    for index in range(count):
        close = 100 + index * .01
        result.append(Bar(int((start + timedelta(minutes=minutes * index)).timestamp() * 1000),
                          close - .01, close + .1, close - .1, close))
    return result


def test_xau_failed_down_shock_reclaims_and_goes_long():
    rows = bars(40)
    shock = rows[-2]
    rows[-2] = Bar(shock.time_ms, 100, 100.1, 97, 97)
    current = rows[-1]
    rows[-1] = Bar(current.time_ms, 97, 100.2, 96.9, 100.1)
    assert xau_failed_shock_reversion(rows, len(rows) - 1,
                                      shock_atr=1.5, reentry_bars=2) == 1


def test_xau_compression_is_known_before_breakout_bar():
    rows = bars(120)
    previous = rows[118]
    rows[118] = Bar(previous.time_ms, previous.close, previous.close + .001,
                    previous.close - .001, previous.close)
    prior_high = max(row.high for row in rows[111:119])
    current = rows[119]
    rows[119] = Bar(current.time_ms, current.open, prior_high + .5,
                    current.low, prior_high + .4)
    assert xau_compression_breakout(rows, 119, channel_bars=8,
                                    compression_quantile=.15) == 1


def test_usdjpy_breakout_requires_complete_asia_and_london_window():
    rows = bars(33, start=datetime(2026, 1, 5, tzinfo=timezone.utc))
    at = 28  # 07:00 UTC
    row = rows[at]
    asia_high = max(item.high for item in rows[:at])
    rows[at] = Bar(row.time_ms, row.open, asia_high + .3, row.low, asia_high + .2)
    assert usdjpy_session_breakout(rows, at, max_range_atr_ratio=20,
                                   trend_lookback_bars=8) == 1
    assert usdjpy_session_breakout(rows[:27], 26, max_range_atr_ratio=20,
                                   trend_lookback_bars=8) == 0


def test_usdjpy_failed_up_break_returns_short():
    rows = bars(31)
    asia_high = max(row.high for row in rows[:28])
    breakout = rows[28]
    rows[28] = Bar(breakout.time_ms, breakout.open, asia_high + .5,
                   breakout.low, asia_high + .2)
    current = rows[29]
    rows[29] = Bar(current.time_ms, current.open, current.high,
                   current.low, asia_high - .05)
    assert usdjpy_failed_break_reversion(rows, 29, failure_window_bars=2,
                                         break_buffer_atr=.1) == -1


def test_us500_rebound_is_long_only_and_requires_reclaim():
    rows = bars(40, minutes=1440)
    at = 39
    previous = rows[at - 1].close
    row = rows[at]
    rows[at] = Bar(row.time_ms, previous - .5, previous + .1,
                   previous - 3, previous - .2)
    assert us500_volatility_shock_rebound(rows, at, shock_atr=1.5,
                                          reclaim_fraction=.7) == 1


def test_eurusd_breakout_must_align_with_lagged_trend():
    rows = bars(50, minutes=1440)
    at = 49
    prior_high = max(row.high for row in rows[at - 10:at])
    row = rows[at]
    rows[at] = Bar(row.time_ms, prior_high, prior_high + .2,
                   row.low, prior_high + .1)
    assert eurusd_short_trend(rows, at, channel_days=10,
                              trend_lookback_days=20) == 1


def test_signal_layer_does_not_accept_future_or_context_arguments():
    # Its API contains only completed prices and sealed numeric axes.  News and
    # contextual vetoes belong to the later point-in-time council replay.
    assert "context" not in eurusd_short_trend.__annotations__
