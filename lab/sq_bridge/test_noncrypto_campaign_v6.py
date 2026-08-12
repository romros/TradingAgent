import hashlib, json
from lab.sq_bridge.noncrypto_campaign_v6 import SEALED, SPEC


def test_v6_preregistration_is_still_sealed():
    assert hashlib.sha256(SPEC.read_bytes()).hexdigest() == SEALED


def test_v6_results_never_opened_future_periods():
    path=SPEC.parent/"evidence/noncrypto_campaign_v6_results.json"
    value=json.loads(path.read_text())
    assert value["train_combinations"]==153
    assert value["train_passes"]==0
    assert value["selected_for_validation"]==0
    assert value["oos_accessed"] is False
    assert value["holdout_accessed"] is False
    assert value["retuned"] is False


def test_every_v6_family_was_executed_with_three_exits():
    spec=json.loads(SPEC.read_text()); result=json.loads((SPEC.parent/"evidence/noncrypto_campaign_v6_results.json").read_text())
    observed={row["family"] for row in result["train"]}
    assert observed=={row["id"] for row in spec["families"]}
    for family in observed:
        assert len({row["exit"] for row in result["train"] if row["family"]==family})==3
