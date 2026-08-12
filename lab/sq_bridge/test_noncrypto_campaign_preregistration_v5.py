import json

import pytest

from lab.sq_bridge.noncrypto_campaign_preregistration_v5 import PREREG, ROOT, verify


def _mutate(tmp_path, mutate):
    doc = json.loads(PREREG.read_text(encoding="utf-8"))
    mutate(doc)
    path = tmp_path / "prereg.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_real_preregistration_is_sealed_before_performance():
    result = verify()
    assert result["decision"] == "PASS_NONCRYPTO_CAMPAIGN_PREREGISTRATION"
    assert result["hypothesis_count"] == 6
    assert result["maximum_evaluations_global"] == 76800
    assert result["maximum_accepted_candidates"] == 48
    assert result["maximum_holdout_candidates"] == 12
    assert result["performance_accessed"] is False
    assert result["holdout_accessed"] is False
    assert result["paper_authorized"] is False

    receipt = json.loads((ROOT / "lab/sq_bridge/evidence/noncrypto_campaign_preregistration_v5_receipt.json").read_text())
    assert receipt["decision"] == result["decision"]
    assert receipt["preregistration_sha256"] == result["preregistration_sha256"]
    assert receipt["performance_accessed"] is False
    assert receipt["holdout_accessed"] is False


def test_rejects_holdout_or_performance_access(tmp_path):
    with pytest.raises(ValueError, match="holdout_accessed"):
        verify(_mutate(tmp_path, lambda d: d.__setitem__("holdout_accessed", True)))
    with pytest.raises(ValueError, match="performance_accessed"):
        verify(_mutate(tmp_path, lambda d: d.__setitem__("performance_accessed", True)))


def test_rejects_temporal_overlap(tmp_path):
    def mutate(doc):
        doc["temporal_splits"]["USDJPY_M15"]["holdout"][0] = "2024-12-31"
    with pytest.raises(ValueError, match="temporal overlap"):
        verify(_mutate(tmp_path, mutate))


def test_rejects_changed_budget_or_extra_axis(tmp_path):
    def budget(doc):
        doc["sq_generation"]["maximum_evaluations_global"] += 1
    with pytest.raises(ValueError, match="global evaluation budget"):
        verify(_mutate(tmp_path, budget))

    def axis(doc):
        doc["hypothesis_search_spaces"][0]["axes"]["fourth"] = [1, 2]
    with pytest.raises(ValueError, match="too many sensitive axes"):
        verify(_mutate(tmp_path, axis))


def test_rejects_catalog_hash_drift(tmp_path):
    def mutate(doc):
        doc["inputs"]["hypothesis_catalog_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="catalog hash mismatch"):
        verify(_mutate(tmp_path, mutate))
