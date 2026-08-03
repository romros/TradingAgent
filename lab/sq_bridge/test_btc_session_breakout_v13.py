import pandas as pd

from lab.sq_bridge.btc_session_breakout_v13 import parameter_grid, session_signal, stable_selection


def hourly(days=3):
    index = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
                          "complete": True}, index=index)
    return frame


def params(**changes):
    value = {"session_start_utc": 0, "day_group": "weekday", "range_hours": 2,
             "mode": "breakout", "trade_window_hours": 4, "stop_atr": 1.5, "hold_bars": 2, "side": "long"}
    value.update(changes); return value


def test_session_range_is_frozen_and_only_first_breakout_signals():
    frame = hourly()
    frame.loc[pd.Timestamp("2024-01-01 02:00", tz="UTC"), "close"] = 102
    frame.loc[pd.Timestamp("2024-01-01 03:00", tz="UTC"), "close"] = 103
    signal = session_signal(frame, params())
    assert list(signal[signal].index) == [pd.Timestamp("2024-01-01 02:00", tz="UTC")]


def test_incomplete_range_blocks_session():
    frame = hourly(); frame.loc[pd.Timestamp("2024-01-01 01:00", tz="UTC"), "complete"] = False
    frame.loc[pd.Timestamp("2024-01-01 02:00", tz="UTC"), "close"] = 102
    assert not session_signal(frame, params()).any()


def test_fade_long_triggers_only_on_downside_break():
    frame = hourly()
    frame.loc[pd.Timestamp("2024-01-01 02:00", tz="UTC"), "close"] = 98
    signal = session_signal(frame, params(mode="fade", side="long"))
    assert list(signal[signal].index) == [pd.Timestamp("2024-01-01 02:00", tz="UTC")]


def test_registered_grid_has_exactly_288_points():
    config = {"grid": {"session_start_utc": [0, 8, 16], "day_group": ["weekday", "weekend"],
                       "mode": ["breakout"],
                       "range_hours": [2, 4], "trade_window_hours": [4, 8], "stop_atr": [1.5, 2.5],
                       "hold_bars": [2, 4, 8], "side": ["long", "short"], "points": 288}}
    assert len(list(parameter_grid(config))) == 288


def test_stability_never_treats_categorical_groups_as_neighbours():
    config = {"grid": {"session_start_utc": [0, 8], "day_group": ["weekday"], "side": ["long"],
                       "mode": ["breakout"],
                       "range_hours": [2, 4], "trade_window_hours": [4], "stop_atr": [1.5], "hold_bars": [2]},
              "stability": {"minimum_passing_neighbours": 1}}
    rows = []
    for hour in (0, 8):
        for range_hours in (2, 4):
            p = {"session_start_utc": hour, "day_group": "weekday", "mode": "breakout", "side": "long", "range_hours": range_hours,
                 "trade_window_hours": 4, "stop_atr": 1.5, "hold_bars": 2}
            rows.append({"candidate_id": f"{hour}-{range_hours}", "parameters": p, "passes_point_gate": True})
    _, selected = stable_selection(config, rows)
    assert len(selected) == 2
