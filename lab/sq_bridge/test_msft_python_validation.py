import pandas as pd

from msft_python_validation import Evaluator


def test_month_boundary_does_not_treat_dataset_edges_as_calendar_events():
    index = pd.to_datetime(["2024-01-15", "2024-01-16", "2024-02-01", "2024-02-02"])
    frame = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1}, index=index)
    evaluator = Evaluator(frame)
    first = evaluator.series({"op": "IsMonthFirstTradingDay", "params": {}})
    last = evaluator.series({"op": "IsMonthLastTradingDay", "params": {}})
    assert list(first) == [False, False, True, False]
    assert list(last) == [False, True, False, False]
