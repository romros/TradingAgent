import json
from datetime import date
from pathlib import Path

import pandas as pd

from lab.sq_bridge.usdjpy_gotobi_tokyo_fix_v27 import event_dates, metrics, stable_neighbors


CONFIG = json.loads(Path(__file__).with_name("family_usdjpy_gotobi_tokyo_fix_v27.json").read_text())


def test_campaign_is_train_only_and_attempt_budget_is_exact():
    assert CONFIG["splits"]["train"] == ["2007-01-01", "2014-12-31"]
    assert CONFIG["splits"]["sealed_holdout"][0] == "2024-01-01"
    assert CONFIG["search"]["attempt_budget"] == 8
    assert CONFIG["economics"]["capital_usdc"] == 200
    assert CONFIG["validation_accessed"] is False and CONFIG["holdout_evaluated"] is False


def test_weekend_mode_moves_only_weekends_to_previous_weekday():
    available = {date(2026, 8, day) for day in range(1, 32) if pd.Timestamp(2026, 8, day).weekday() < 5}
    exact = event_dates(available, "exact_calendar")
    adjusted = event_dates(available, "weekend_previous_business_day")
    assert date(2026, 8, 10) in exact and date(2026, 8, 10) in adjusted
    assert date(2026, 8, 14) in adjusted  # Saturday 15th moves to Friday.
    assert date(2026, 8, 14) not in exact


def test_refunded_oracle_is_not_charged_in_base_but_stress_can_charge_it():
    trades = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"], utc=True),
                           "gross_return": [.01], "adverse_fraction": [.001], "stop_fraction": [.0025]})
    base = metrics(trades, 0, 0, CONFIG["economics"])
    stress = metrics(trades, 0, .1, CONFIG["economics"])
    assert base["expectancy_usdc"] == 8.0
    assert stress["expectancy_usdc"] == 7.9
    assert base["effective_leverage"] == 4


def test_stability_requires_adjacent_frozen_point():
    axes = [["exact", "adjusted"], [7, 8], [.0015, .0025]]
    passing = {("exact", 7, .0015), ("exact", 8, .0015)}
    assert stable_neighbors(("exact", 7, .0015), passing, axes) == 1
