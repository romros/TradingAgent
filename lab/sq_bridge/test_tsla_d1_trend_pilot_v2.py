import json
from pathlib import Path


def test_tsla_campaign_is_blind_price_only_and_sealed():
    spec = json.loads(Path(__file__).with_name("tsla_d1_trend_pilot_v2.json").read_text())
    assert spec["performance_accessed_before_freeze"] is False
    assert spec["volume_rules_allowed"] is False
    assert spec["periods"]["train_to"] < spec["periods"]["validation_from"]
    assert spec["periods"]["validation_to"] < spec["periods"]["sealed_oos_from"]
    assert spec["periods"]["sealed_oos_to"] < spec["periods"]["untouched_future_from"]
    assert spec["promotion_allowed"] is False
