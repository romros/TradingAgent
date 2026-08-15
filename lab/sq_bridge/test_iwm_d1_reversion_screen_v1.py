import datetime as dt
import math

from lab.sq_bridge.iwm_d1_reversion_screen_v1 import (
    immediate_neighbours, load, metrics, period, rsi_wilder,
)


def test_rsi_wilder_detects_uninterrupted_decline():
    assert rsi_wilder([10, 9, 8, 7], 2)[-1] == 0


def test_period_requires_entry_and_exit_inside_boundary():
    trade = {"entry": dt.date(2023, 12, 29), "exit": dt.date(2024, 1, 2),
             "return": 0.1, "holding_sessions": 2}
    assert period([trade], dt.date(2024, 1, 1), dt.date(2024, 12, 31)) == []


def test_metrics_compounds_and_computes_profit_factor():
    result = metrics([{"return": 0.1, "holding_sessions": 1},
                      {"return": -0.05, "holding_sessions": 3}])
    assert result["trades"] == 2
    assert math.isclose(result["profit_factor"], 2.0)
    assert math.isclose(result["total_return"], 0.045)
    assert result["average_holding_sessions"] == 2


def test_immediate_neighbours_change_exactly_one_dimension():
    center = (2, 5, 3, 150, 5)
    variants = [center, (3, 5, 3, 150, 5), (3, 10, 3, 150, 5),
                (2, 5, 5, 150, 5)]
    assert immediate_neighbours(center, variants) == [
        (3, 5, 3, 150, 5), (2, 5, 5, 150, 5)]


def test_loads_canonical_sq_d1_without_header(tmp_path):
    source = tmp_path / "IWM_through_2024.csv"
    source.write_text("2024.01.02,00:00,100,102,99,101,7\n")
    assert load(source) == [{"date": dt.date(2024, 1, 2), "open": 100.0,
                             "close": 101.0}]
