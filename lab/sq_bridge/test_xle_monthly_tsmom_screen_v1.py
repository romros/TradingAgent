import datetime as dt
import math

from lab.sq_bridge.xle_monthly_tsmom_screen_v1 import metrics, monthly_reviews


def test_monthly_reviews_returns_last_session():
    rows = [{"date": dt.date(2024, 1, 2)}, {"date": dt.date(2024, 1, 31)},
            {"date": dt.date(2024, 2, 1)}]
    assert monthly_reviews(rows) == [1, 2]


def test_metrics_includes_flat_months_and_compounds():
    trades = [{"entry": dt.date(2024, 1, 2), "exit": dt.date(2024, 1, 31),
               "return": 0.1},
              {"entry": dt.date(2024, 3, 1), "exit": dt.date(2024, 3, 29),
               "return": -0.05}]
    result = metrics(trades, dt.date(2024, 1, 1), dt.date(2024, 3, 31))
    assert result["monthly_observations"] == 3
    assert math.isclose(result["total_return"], 0.045)
    assert math.isclose(result["maximum_drawdown"], 0.05)
