import json

import pytest

from lab.sq_bridge.noncrypto_playbook_hypotheses_v5 import CATALOG, validate


def test_real_catalog_is_new_noncrypto_and_performance_blind():
    result = validate()
    assert result == {
        "decision": "PASS_PREPERFORMANCE_HYPOTHESIS_CATALOG",
        "hypothesis_count": 6,
        "markets": ["EURUSD", "US500", "USDJPY", "XAUUSD"],
        "family_count": 6,
        "performance_accessed": False,
        "holdout_accessed": False,
        "legacy_candidates_reused": False,
    }


def test_each_playbook_has_tp_sl_time_context_and_unmanaged_baseline():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    for item in catalog["hypotheses"]:
        assert item["initial_stop"]
        assert item["take_profit"]
        assert item["max_holding_bars_range"][1] <= 20
        assert item["context_required"] and item["context_veto"]
        assert "NONE" in item["fast_manager_variants"]


def test_rejects_crypto_or_performance_taint(tmp_path):
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["hypotheses"][0]["market"] = "BTCUSD"
    path = tmp_path / "crypto.json"
    path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="not authorized"):
        validate(path)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog["performance_accessed"] = True
    path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError, match="performance_accessed"):
        validate(path)
