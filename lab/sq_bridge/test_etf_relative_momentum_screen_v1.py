import datetime as dt
import math

from lab.sq_bridge.etf_relative_momentum_screen_v1 import metrics, reviews


def test_reviews_uses_last_common_session():
    days = [dt.date(2024, 1, 2), dt.date(2024, 1, 31), dt.date(2024, 2, 1)]
    assert reviews(days) == [1, 2]


def test_metrics_compounds_monthly_returns():
    rows = [{"return": 0.1, "selected": ["A", "B"]},
            {"return": -0.05, "selected": ["A"]}]
    result = metrics(rows)
    assert math.isclose(result["total_return"], 0.045)
    assert result["cash_slot_months"] == 1
