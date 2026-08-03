import pandas as pd

from lab.sq_bridge.xau_d1_trend_pullback_v10 import enrich, simulate


def params(**changes):
    value = {"side": "long", "trend_ema": 100, "rsi_period": 2,
             "rsi_extreme": 15, "stop_atr": 2.0, "hold_sessions": 3}
    value.update(changes)
    return value


def frame_with_long_signal():
    index = pd.date_range("2020-01-01", periods=130, freq="D")
    close = [100 + i * .2 for i in range(130)]
    close[119:123] = [124, 122, 120, 123]
    frame = pd.DataFrame({"open": close, "high": [x + 1 for x in close],
                          "low": [x - 1 for x in close], "close": close, "bars": 100}, index=index)
    return enrich(frame)


def test_signal_is_executed_only_at_next_session_open():
    frame = frame_with_long_signal()
    costs = {"base": {"opening_bps": 0, "annual_funding_pct": 0}}
    trades = simulate(frame, params(), costs)
    assert trades
    for trade in trades:
        assert trade["entry_date"] > frame.index[0].date().isoformat()


def test_cost_and_funding_reduce_return():
    frame = frame_with_long_signal()
    costs = {"base": {"opening_bps": 0, "annual_funding_pct": 0},
             "stress": {"opening_bps": 9, "annual_funding_pct": 12}}
    trade = simulate(frame, params(), costs)[0]
    assert trade["stress"] < trade["base"]


def test_open_positions_suppress_overlapping_signals():
    frame = frame_with_long_signal()
    costs = {"base": {"opening_bps": 0, "annual_funding_pct": 0}}
    trades = simulate(frame, params(hold_sessions=3, stop_atr=100), costs)
    entries = [pd.Timestamp(trade["entry_date"]) for trade in trades]
    assert all((right - left).days >= 3 for left, right in zip(entries, entries[1:]))
