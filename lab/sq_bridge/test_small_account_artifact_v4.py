import json
from pathlib import Path

from lab.sq_bridge.small_account_artifact_v4 import build_artifact, evaluate_trace
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _robustness(tmp_path, candidate_ids=("candidate",)):
    metrics = {candidate: {
        "monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .8,
        "parameter_variant_count": 4,
        "profitable_parameter_variants_ratio": .75,
        "stress_profit_factor": 1.2, "liquidation_probability": 0,
        "tested_leverage": 5, "venue_max_leverage": 100,
        "liquidation_distance_pct": 19.75,
    } for candidate in candidate_ids}
    path = tmp_path / "robustness.json"
    path.write_text(json.dumps({
        "schema_version": 1, "stage": "robustness", "campaign_id": "campaign",
        "decision": "PASS", "candidate_ids": list(candidate_ids),
        "candidate_robustness_metrics": metrics}, indent=2, sort_keys=True) + "\n")
    return path


def _trace(candidate_id="candidate", *, win=.5, loss=-.25):
    return {
        "schema_version": 1, "trace_type": "small_account_trade_trace",
        "candidate_id": candidate_id, "capital_usdc": 200,
        "holdout_accessed": False, "stop_loss_required": True,
        "risk_per_trade_pct": 1.5, "stop_distance_pct": 1,
        "venue_max_leverage": 100, "cost_model_sha256": "a" * 64,
        "trades": [{"trade_id": f"trade-{index:02d}",
                    "net_return_pct_by_cost": {
                        "base": win if index < 18 else loss,
                        "conservative": win - .1 if index < 18 else loss - .025,
                        "stress": win - .2 if index < 18 else loss - .05}}
                   for index in range(30)],
    }


def _write(tmp_path, trace):
    path = tmp_path / f"{trace['candidate_id']}.small-account.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_small_account_recomputes_performance_sizing_and_real_contract(tmp_path):
    robustness = _robustness(tmp_path)
    trace = _write(tmp_path, _trace())
    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace],
        robustness_artifact_path=robustness,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["selected_leverage"] == 5
    assert artifact["position_notional_usdc"] == 300
    assert artifact["collateral_usdc"] == 60
    assert set(artifact["higher_leverage_rejection_reasons"]) == {
        "8", "10", "15", "20", "30", "50", "75", "100"}
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "small_account_economics", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_small_account_selects_best_worst_cost_expectancy_deterministically(tmp_path):
    robustness = _robustness(tmp_path, ("a", "b"))
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, _trace("a", win=.45)),
                     _write(tmp_path, _trace("b", win=.55))],
        robustness_artifact_path=robustness,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "selected.json")
    assert artifact["candidate_ids"] == ["b"]
    assert set(artifact["evaluated_candidate_small_account_metrics"]) == {"a", "b"}


def test_small_account_trace_tampering_is_detected(tmp_path):
    robustness = _robustness(tmp_path)
    value = _trace()
    trace = _write(tmp_path, value)
    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace],
        robustness_artifact_path=robustness,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    value["trades"][0]["net_return_pct_by_cost"]["stress"] = 10
    trace.write_text(json.dumps(value))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "small_account_economics", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:small_account_economics:SOURCE_TRACE_CONTRACT" in errors


def test_realized_gap_loss_above_three_percent_rejects_candidate(tmp_path):
    robustness = _robustness(tmp_path)
    trace = _trace(win=3, loss=-.25)
    trace["trades"][-1]["net_return_pct_by_cost"] = {
        "base": -3, "conservative": -3, "stress": -3}
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace)],
        robustness_artifact_path=robustness,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []


def test_eurusd_venue_maximum_is_evaluated_and_must_be_rejected_explicitly():
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    trace = _trace()
    trace["venue_max_leverage"] = 200
    result = evaluate_trace(trace, methodology["small_account"], {
        "tested_leverage": 100, "venue_max_leverage": 200})
    assert result["evaluated_leverage_grid"][-2:] == [150, 200]
    assert set(result["higher_leverage_rejection_reasons"]) >= {"150", "200"}
    assert "exceeds_robustness_tested_leverage" in result[
        "higher_leverage_rejection_reasons"]["200"]
