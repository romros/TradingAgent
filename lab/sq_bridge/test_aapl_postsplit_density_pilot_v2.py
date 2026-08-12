import json

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
