import json

from pathlib import Path

from lab.sq_bridge.aapl_postsplit_density_pilot_v2 import SPEC


def test_pilot_is_postsplit_blind_and_non_promotable():
    spec = json.loads(SPEC.read_text())
    assert spec["periods"]["train_from"] == "2020-08-31"
    assert spec["periods"]["train_to"] < spec["periods"]["validation_from"]
    assert spec["periods"]["validation_to"] < spec["periods"]["sealed_oos_from"]
    assert spec["periods"]["untouched_future_from"] == "2025-01-01"
    assert spec["performance_accessed_before_freeze"] is False
    assert spec["promotion_allowed"] is False
    assert spec["paper_authorized"] is False
    assert spec["live_authorized"] is False


def test_idea_harvest_is_loose_but_still_sealed_and_non_promotable():
    path = Path(__file__).with_name("aapl_postsplit_idea_harvest_v2.json")
    spec = json.loads(path.read_text())
    assert spec["discovery"]["direction"] == "both"
    assert spec["discovery"]["minimum_train_trades"] == 8
    assert spec["discovery"]["minimum_profit_factor_train"] == 1.05
    assert spec["periods"]["validation_from"] > spec["periods"]["train_to"]
    assert spec["periods"]["sealed_oos_from"] > spec["periods"]["validation_to"]
    assert spec["promotion_allowed"] is False


def test_h4_harvest_is_a_frequency_escalation_not_holdout_relaxation():
    path = Path(__file__).with_name("aapl_postsplit_h4_idea_harvest_v2.json")
    spec = json.loads(path.read_text())
    assert spec["discovery"]["timeframe"] == "H4"
    assert spec["discovery"]["minimum_train_trades"] == 30
    assert spec["periods"]["validation_from"] == "2023-01-03"
    assert spec["periods"]["sealed_oos_from"] == "2024-01-02"
    assert spec["promotion_allowed"] is False
