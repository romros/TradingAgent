import json
import hashlib
from pathlib import Path

import pytest

from lab.sq_bridge.robustness_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _trace(candidate_id="candidate", *, profitable_runs=700,
           profitable_variants=3, tested_leverage=5):
    return {
        "schema_version": 1, "trace_type": "robustness_simulation_trace",
        "source": "synthetic_control",
        "monte_carlo_method": "iid_observed_trade_bootstrap_with_replacement",
        "monte_carlo_seed": 20260811,
        "parameter_variant_method": "strategyquant_RandomizeStrategyParameters",
        "parameter_probability_pct": 10,
        "candidate_id": candidate_id, "capital_usdc": 200,
        "holdout_accessed": False, "tested_leverage": tested_leverage,
        "venue_max_leverage": 100,
        "liquidation_model": "ostium_threshold_cost_buffered", "cost_stress_multiplier": 2,
        "cost_model_sha256": "", "evaluation_notional_usdc": 200,
        "monte_carlo_runs": [
            {"run_id": f"run-{index:04d}",
             "gross_pnl_usdc": 1.0 if index < profitable_runs else -1.0,
             "trade_count": 30, "long_holding_days": 15,
             "short_holding_days": 15,
             "maximum_adverse_excursion_pct": 2.0,
             "maximum_adverse_excursion_side": "long" if index % 2 == 0 else "short",
             "maximum_adverse_excursion_holding_days": 1.0}
            for index in range(1000)],
        "parameter_variants": [
            {"variant_id": f"variant-{index}",
             "maximum_perturbation_pct": 10,
             "gross_pnl_usdc": 1.0 if index < profitable_variants else -1.0,
             "trade_count": 30, "long_holding_days": 15,
             "short_holding_days": 15}
            for index in range(4)],
        "stress_trades": [
            {"gross_return_pct": .5 if index < 18 else -.25,
             "side": "long" if index % 2 == 0 else "short", "holding_days": 1}
            for index in range(30)],
    }


def _cost_model(tmp_path):
    path = tmp_path / "costs.json"
    carry = {scenario + "_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    path.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {"base_roundtrip_bps": 0,
                                  "conservative_roundtrip_bps": 0,
                                  "stress_roundtrip_bps": 0}},
        "carry": {"long": carry, "short": carry}}, sort_keys=True) + "\n")
    return path


def _write(tmp_path, trace, costs):
    trace["cost_model_sha256"] = hashlib.sha256(costs.read_bytes()).hexdigest()
    path = tmp_path / f"{trace['candidate_id']}.robustness.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_robustness_artifact_recomputes_all_trials_and_passes_contract(tmp_path):
    costs = _cost_model(tmp_path)
    trace_path = _write(tmp_path, _trace(), costs)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        cost_model_path=costs,
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
    costs = _cost_model(tmp_path)
    trace_path = _write(tmp_path, trace, costs)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    trace["monte_carlo_runs"][999]["gross_pnl_usdc"] = 100
    trace_path.write_text(json.dumps(trace))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "robustness", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:robustness:TRACE_CONTRACT" in errors


def test_unstable_parameter_region_rejects_candidate(tmp_path):
    costs = _cost_model(tmp_path)
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, _trace(profitable_variants=2), costs)],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "REJECT", "candidate_ids": [],
               "holdout_accessed": False,
               "artifact": str(tmp_path / "reject.json")}
    assert validate_stage_artifact(
        "robustness", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_liquidation_probability_is_derived_from_adverse_excursion(tmp_path):
    costs = _cost_model(tmp_path)
    trace = _trace()
    trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] = 20.0
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace, costs)],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "one-liquidation.json")
    assert artifact["decision"] == "PASS"
    assert artifact["liquidation_probability"] == .001

    trace = _trace("two-liquidations")
    trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] = 20.0
    trace["monte_carlo_runs"][1]["maximum_adverse_excursion_pct"] = 20.0
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace, costs)],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "two-liquidations.json")
    assert artifact["decision"] == "REJECT"


def test_execution_cost_buffer_can_turn_nominally_safe_mae_into_liquidation(tmp_path):
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    model["by_notional"]["200"]["stress_roundtrip_bps"] = 10
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")
    trace = _trace()
    # Nominal distance at 5x / venue 100x is 19.75%; the conservative
    # full-roundtrip buffer reduces it to 19.65%.
    trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] = 19.70
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace, costs)],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "cost-buffered-liquidation.json")
    metrics = artifact["evaluated_candidate_robustness_metrics"]["candidate"]
    assert metrics["nominal_liquidation_distance_pct"] == pytest.approx(19.75)
    assert metrics["liquidation_distance_pct"] == pytest.approx(19.65)
    assert metrics["liquidation_probability"] == .001


def test_robustness_rejects_unregistered_leverage_and_early_holdout(tmp_path):
    costs = _cost_model(tmp_path)
    with pytest.raises(ValueError, match="fora de la graella"):
        build_artifact(
            campaign_id="campaign",
            trace_paths=[_write(tmp_path, _trace(tested_leverage=7), costs)],
            cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "leverage.json")
    trace = _trace("holdout")
    trace["holdout_accessed"] = True
    with pytest.raises(ValueError, match="sense obrir holdout"):
        build_artifact(
            campaign_id="campaign", trace_paths=[_write(tmp_path, trace, costs)],
            cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "holdout.json")


def test_robustness_recomputes_stress_costs_and_detects_model_tampering(tmp_path):
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    model["by_notional"]["200"]["stress_roundtrip_bps"] = 5
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")
    trace = _trace()
    for row in trace["monte_carlo_runs"][:700]:
        row["gross_pnl_usdc"] = 4
    for row in trace["parameter_variants"][:3]:
        row["gross_pnl_usdc"] = 4
    trace_path = _write(tmp_path, trace, costs)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path], cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["evaluated_candidate_robustness_metrics"]["candidate"][
        "profitable_monte_carlo_ratio"] == .7
    assert artifact["evaluated_candidate_robustness_metrics"]["candidate"][
        "robust_roundtrip_bps"] == 5

    costs.write_text("{}\n")
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "robustness", artifact, receipt,
        json.loads((ROOT / "methodology_v4.json").read_text()),
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:robustness:TRACE_CONTRACT" in errors
