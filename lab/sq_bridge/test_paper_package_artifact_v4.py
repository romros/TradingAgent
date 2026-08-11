import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.e2e_control import payload
from lab.sq_bridge.paper_package_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sources(tmp_path):
    candidate = "candidate"
    result = {}
    costs = tmp_path / "costs.json"
    _write(costs, {"decision": "PASS_COSTS_FROZEN", "costs_frozen": True})
    for stage, holdout in (("market_preflight", False),
                           ("small_account_economics", False),
                           ("final_holdout_validation", True),
                           ("python_translation", False), ("parity", False)):
        ids = [] if stage == "market_preflight" else [candidate]
        value = payload(stage, ids, holdout)
        value.update({"campaign_id": "campaign", "evidence_class": "observed"})
        value.pop("control_purpose", None)
        path = tmp_path / f"{stage}.json"
        result[stage] = path
        if stage == "python_translation":
            ir = tmp_path / "candidate.ir.json"
            _write(ir, {"strategy_id": candidate})
            value.update({"canonical_ir_path": ir.name,
                          "canonical_ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest()})
        if stage == "parity":
            report = tmp_path / "candidate.parity.json"
            _write(report, {"candidate_id": candidate})
            value.update({"parity_report_path": report.name,
                          "parity_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()})
        if stage == "small_account_economics":
            value.update({
                "minimum_position_notional_usdc": 150,
                "maximum_position_notional_usdc": value["position_notional_usdc"],
                "venue_minimum_notional_usdc": 5,
                "cost_model_path": costs.name,
                "cost_model_sha256": hashlib.sha256(costs.read_bytes()).hexdigest(),
            })
        _write(path, value)
    return result


def _build(tmp_path):
    paths = _sources(tmp_path)
    artifact_path = tmp_path / "paper-stage.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", source_artifact_paths=paths,
        config_path=tmp_path / "paper.json", artifact_path=artifact_path)
    return artifact, artifact_path


def test_paper_package_binds_ostium_risk_ir_and_parity_without_signer(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    config = json.loads((tmp_path / "paper.json").read_text())
    assert config["ostium_pair_id"] == "control-pair"
    assert config["selected_leverage"] == 5
    assert config["capital_committed_usdc"] == 60
    assert config["reserve_usdc"] == 140
    assert config["risk_per_trade_pct"] == 1.5
    assert config["sizing_policy"] == (
        "risk_budget_over_runtime_initial_stop_capped_by_validated_notional")
    assert config["dynamic_stop_sizing"] is True
    assert config["minimum_position_notional_usdc"] == 150
    assert config["maximum_position_notional_usdc"] == 300
    assert config["venue_minimum_notional_usdc"] == 5
    assert len(config["cost_model_sha256"]) == 64
    assert config["stop_loss_required"] is True
    assert config["mode"] == "paper"
    assert config["signer_enabled"] is config["live_authorized"] is False
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "paper", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_config_cannot_raise_leverage_after_validation_even_if_rehashed(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    config_path = tmp_path / "paper.json"
    config = json.loads(config_path.read_text())
    config["selected_leverage"] = 100
    _write(config_path, config)
    artifact["paper_config_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "paper", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:paper:PACKAGE_CONTRACT" in errors


def test_package_rejects_source_artifact_from_another_candidate(tmp_path):
    paths = _sources(tmp_path)
    parity = json.loads(paths["parity"].read_text())
    parity["candidate_ids"] = ["other"]
    _write(paths["parity"], parity)
    with pytest.raises(ValueError, match="lineage mismatch"):
        build_artifact(
            campaign_id="campaign", candidate_id="candidate", source_artifact_paths=paths,
            config_path=tmp_path / "paper.json", artifact_path=tmp_path / "stage.json")
