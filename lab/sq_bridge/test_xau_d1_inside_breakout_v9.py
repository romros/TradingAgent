import pandas as pd

from lab.sq_bridge.xau_d1_inside_breakout_v9 import enrich, metrics, simulate


def params(**changes):
    value = {"side": "long", "inside_range_ratio_max": 1.0, "trend_ema": 0,
             "atr_period": 14, "entry_buffer_atr": 0.0, "stop_atr": 1.0,
             "target_atr": 2.0, "hold_sessions": 1}
    value.update(changes)
    return value


def test_inside_signal_enters_next_session_without_lookahead():
    index = pd.date_range("2020-01-01", periods=18, freq="D")
    frame = pd.DataFrame({"open": 100., "high": 102., "low": 98., "close": 100., "bars": 100}, index=index)
    frame.loc[index[15], ["high", "low", "close"]] = [101., 99., 100.]
    frame.loc[index[16], ["open", "high", "low", "close"]] = [100., 103., 100., 102.]
    trades = simulate(enrich(frame), params(), {"stress": {"opening_bps": 9, "annual_funding_pct": 12}})
    assert trades[0]["entry_date"] == "2020-01-17"
    assert trades[0]["gross_return"] > 0


def test_adverse_gap_cannot_fill_at_better_trigger_price():
    index = pd.date_range("2020-01-01", periods=18, freq="D")
    frame = pd.DataFrame({"open": 100., "high": 102., "low": 98., "close": 100., "bars": 100}, index=index)
    frame.loc[index[15], ["high", "low"]] = [101., 99.]
    frame.loc[index[16], ["open", "high", "low", "close"]] = [105., 106., 104., 104.]
    trades = simulate(enrich(frame), params(), {"base": {"opening_bps": 0, "annual_funding_pct": 0}})
    assert trades[0]["gross_return"] < 0


def test_metrics_include_costs_and_year_stability():
    trades = [{"exit_date": "2020-01-01", "stress": .01}, {"exit_date": "2021-01-01", "stress": -.005}]
    result = metrics(trades, "stress")
    assert result["trades"] == 2
    assert result["profit_factor"] == 2
    assert result["positive_year_ratio"] == .5


def test_signals_do_not_create_overlapping_positions():
    index = pd.date_range("2020-01-01", periods=22, freq="D")
    frame = pd.DataFrame({"open": 100., "high": 102., "low": 98., "close": 100., "bars": 100}, index=index)
    frame.loc[index[15], ["high", "low"]] = [101.5, 98.5]
    frame.loc[index[16], ["high", "low", "close"]] = [101., 99., 100.]
    frame.loc[index[17], ["high", "low", "close"]] = [103., 99.5, 101.]
    frame.loc[index[18], ["high", "low", "close"]] = [103., 99.5, 101.]
    costs = {"base": {"opening_bps": 0, "annual_funding_pct": 0}}
    trades = simulate(enrich(frame), params(hold_sessions=3, stop_atr=10, target_atr=10), costs)
    assert len(trades) == 1
