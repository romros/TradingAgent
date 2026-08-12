import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_ibkr_aggressive_contract_is_fail_closed_and_reproducible():
    spec = json.loads((ROOT / "lab/sq_bridge/ibkr_aggressive_preregistration_v1.json").read_text())
    source = ROOT / spec["data"]["path"]
    universe = json.loads((ROOT / spec["venue"]["tradable_universe_registry"]).read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == spec["data"]["sha256"]
    assert spec["venue"]["minimum_margin_account_equity_eur"] == 2000
    assert spec["venue"]["maximum_leverage_from_published_initial_margin"] == 16
    assert universe["assets"][spec["venue"]["instrument"]]["status"] == "WEB_VERIFIED"
    assert universe["assets"][spec["venue"]["instrument"]]["minimum_order_units"] == 1
    assert spec["execution"]["minimum_roundtrip_commission_usd"] == 2
    assert spec["temporal_contract"]["prospective_holdout_accessed"] is False
    assert spec["paper_or_live_authorized"] is False
    assert spec["research_pipeline"]["primary_discovery_engine"] == "StrategyQuant SQCLI"
    assert spec["research_pipeline"]["sq_must_precede_python_candidate_promotion"] is True
    assert spec["model_policy"]["model_may"] == [
        "veto_trade", "reduce_risk", "classify_pre_entry_regime"]
    assert "create_entry" in spec["model_policy"]["model_may_not"]


def test_new_session_handoff_closes_ostium_objective():
    handoff = (ROOT / "CURRENT_OBJECTIVE.md").read_text()
    readme = (ROOT / "README.md").read_text()
    assistant_rules = (ROOT / "CLAUDE.md").read_text()
    assert "Objectiu anterior — TANCAT" in handoff
    assert "IBKR" in handoff and "200, 400, 500, 700, 1.000 i 2.000" in handoff
    assert "50% anual" in handoff and "mai una garantia" in handoff
    assert "CURRENT_OBJECTIVE.md" in readme
    assert "Llegeix CURRENT_OBJECTIVE.md abans" in assistant_rules
    assert "No s'han de reprendre" in handoff
    assert "StrategyQuant/SQCLI és el motor principal" in handoff
