import json
from pathlib import Path

import pytest

from lab.sq_bridge.robustness_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _trace(candidate_id="candidate", *, profitable_runs=700,
           profitable_variants=3, tested_leverage=5):
    return {
        "schema_version": 1, "trace_type": "robustness_simulation_trace",
        "candidate_id": candidate_id, "capital_usdc": 200,
        "holdout_accessed": False, "tested_leverage": tested_leverage,
        "venue_max_leverage": 100,
        "liquidation_model": "ostium_exact", "cost_stress_multiplier": 2,
        "cost_model_sha256": "a" * 64,
        "monte_carlo_runs": [
            {"run_id": f"run-{index:04d}",
             "net_pnl_usdc": 1.0 if index < profitable_runs else -1.0,
             "maximum_adverse_excursion_pct": 2.0} for index in range(1000)],
        "parameter_variants": [
            {"variant_id": f"variant-{index}",
             "perturbation_pct": -10 if index % 2 == 0 else 10,
             "net_pnl_usdc": 1.0 if index < profitable_variants else -1.0}
            for index in range(4)],
        "stress_trade_pnl_usdc": [
            1.0 if index < 18 else -.5 for index in range(30)],
    }


def _write(tmp_path, trace):
    path = tmp_path / f"{trace['candidate_id']}.robustness.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_robustness_artifact_recomputes_all_trials_and_passes_contract(tmp_path):
    trace_path = _write(tmp_path, _trace())
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["profitable_monte_carlo_ratio"] == .7
    assert artifact["profitable_parameter_variants_ratio"] == .75
    assert artifact["maximum_tested_leverage"] == 5
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "robustness", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_robustness_trace_tampering_is_detected(tmp_path):
    trace = _trace()
    trace_path = _write(tmp_path, trace)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    trace["monte_carlo_runs"][999]["net_pnl_usdc"] = 100
    trace_path.write_text(json.dumps(trace))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "robustness", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:robustness:TRACE_CONTRACT" in errors


def test_unstable_parameter_region_rejects_candidate(tmp_path):
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, _trace(profitable_variants=2))],
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []


def test_liquidation_probability_is_derived_from_adverse_excursion(tmp_path):
    trace = _trace()
    trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] = 20.0
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace)],
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "one-liquidation.json")
    assert artifact["decision"] == "PASS"
    assert artifact["liquidation_probability"] == .001

    trace = _trace("two-liquidations")
    trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] = 20.0
    trace["monte_carlo_runs"][1]["maximum_adverse_excursion_pct"] = 20.0
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace)],
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "two-liquidations.json")
    assert artifact["decision"] == "REJECT"


def test_robustness_rejects_unregistered_leverage_and_early_holdout(tmp_path):
    with pytest.raises(ValueError, match="fora de la graella"):
        build_artifact(
            campaign_id="campaign",
            trace_paths=[_write(tmp_path, _trace(tested_leverage=7))],
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "leverage.json")
    trace = _trace("holdout")
    trace["holdout_accessed"] = True
    with pytest.raises(ValueError, match="sense obrir holdout"):
        build_artifact(
            campaign_id="campaign", trace_paths=[_write(tmp_path, trace)],
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "holdout.json")
