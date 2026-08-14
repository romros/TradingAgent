from pathlib import Path

from lab.sq_bridge.turnaround_tuesday_screen_v1 import metrics, trades


def test_signal_uses_first_session_of_week_and_next_two_opens():
    rows = [
        {"date": "2023-01-06", "open": 100.0, "close": 100.0},
        {"date": "2023-01-09", "open": 100.0, "close": 98.0},
        {"date": "2023-01-10", "open": 98.5, "close": 99.0},
        {"date": "2023-01-11", "open": 100.0, "close": 100.0},
    ]
    result = trades(rows, "2023-01-01", "2023-12-31", 30)
    assert len(result) == 1
    assert result[0]["entry"] == "2023-01-10"
    assert result[0]["net_return"] == 100.0 / 98.5 - 1 - 0.003


def test_metrics_compounds_and_counts_years():
    value = metrics([
        {"entry": "2022-01-04", "net_return": 0.1},
        {"entry": "2023-01-03", "net_return": -0.05},
    ])
    assert value["trades"] == 2
    assert round(value["net_return"], 6) == 0.045
    assert value["positive_calendar_years"] == 1
