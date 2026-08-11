import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.final_holdout_artifact_v4 import build_artifact, evaluate_trace
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _trace(cost_hash, sizing_hash, *, evaluation_count=1):
    trades = []
    for index in range(20):
        win = index < 12
        trades.append({
            "trade_id": f"t{index:02d}",
            "gross_return_pct": .5 if win else -.15,
            "side": "long" if index % 2 == 0 else "short",
            "holding_days": 1,
        })
    return {
        "schema_version": 1, "trace_type": "final_holdout_trade_trace",
        "candidate_id": "candidate", "capital_usdc": 200,
        "selection_frozen_before_holdout": True,
        "parameters_changed_after_holdout": False,
        "holdout_evaluation_count": evaluation_count,
        "position_notional_usdc": 200, "selected_leverage": 5,
        "cost_model_sha256": cost_hash,
        "small_account_artifact_sha256": sizing_hash,
        "trades": trades,
    }


def _sources(tmp_path):
    costs = tmp_path / "costs.json"
    carry = {scenario + "_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    costs.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {"base_roundtrip_bps": 0,
                                  "conservative_roundtrip_bps": 10,
                                  "stress_roundtrip_bps": 15}},
        "venue_limits": {"min_notional_usd": {
            "min": 10, "p50": 10, "p95": 10, "max": 10, "n": 30}},
        "carry": {"long": carry, "short": carry}}, sort_keys=True) + "\n")
    cost_hash = hashlib.sha256(costs.read_bytes()).hexdigest()
    sizing = tmp_path / "small-account.json"
    sizing.write_text(json.dumps({
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["candidate"],
        "capital_usdc": 200, "position_notional_usdc": 200,
        "risk_per_trade_pct": 1.5,
        "selected_leverage": 5, "cost_model_sha256": cost_hash,
    }, sort_keys=True) + "\n")
    return costs, sizing, cost_hash, hashlib.sha256(sizing.read_bytes()).hexdigest()


def _build(tmp_path, trace=None):
    costs, sizing, cost_hash, sizing_hash = _sources(tmp_path)
    trace_path = tmp_path / "holdout.trace.json"
    trace_path.write_text(json.dumps(
        trace or _trace(cost_hash, sizing_hash), indent=2, sort_keys=True) + "\n")
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
        small_account_artifact_path=sizing, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    return artifact, artifact_path


def test_holdout_pass_is_recomputed_from_twenty_trade_cost_trace(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    assert artifact["decision"] == "PASS"
    assert artifact["holdout_trades"] == 20
    assert artifact["minimum_holdout_profit_factor"] > 1.1
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_second_holdout_evaluation_is_forbidden(tmp_path):
    costs, sizing, cost_hash, sizing_hash = _sources(tmp_path)
    with pytest.raises(ValueError, match="una vegada"):
        trace_path = tmp_path / "holdout.trace.json"
        trace_path.write_text(json.dumps(_trace(cost_hash, sizing_hash, evaluation_count=2)))
        build_artifact(
            campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
            small_account_artifact_path=sizing, cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "invalid.json")


def test_losing_stress_scenario_rejects_whole_candidate(tmp_path):
    costs, sizing, cost_hash, sizing_hash = _sources(tmp_path)
    trace = _trace(cost_hash, sizing_hash)
    for row in trace["trades"]:
        row["gross_return_pct"] -= .5
    trace_path = tmp_path / "holdout.trace.json"
    trace_path.write_text(json.dumps(trace))
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
        small_account_artifact_path=sizing, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["minimum_holdout_net_expectancy_usdc"] < .1


def test_zero_trade_holdout_is_preserved_as_terminal_reject(tmp_path):
    costs, sizing, cost_hash, sizing_hash = _sources(tmp_path)
    trace = _trace(cost_hash, sizing_hash)
    trace["trades"] = []
    trace_path = tmp_path / "zero.trace.json"
    trace_path.write_text(json.dumps(trace))
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
        small_account_artifact_path=sizing, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "zero.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["holdout_trades"] == 0
    assert artifact["minimum_holdout_profit_factor"] == 0


def test_dynamic_holdout_sizes_each_trade_from_frozen_risk_and_notional_cap(tmp_path):
    costs, sizing, cost_hash, sizing_hash = _sources(tmp_path)
    trace = _trace(cost_hash, sizing_hash)
    trace["schema_version"] = 2
    trace["risk_per_trade_pct"] = 1.5
    for index, row in enumerate(trace["trades"]):
        # 1% would request 300 USDC and is capped at the pre-holdout 200;
        # 3% requests 100 USDC and therefore reduces exposure.
        row["initial_stop_distance_pct"] = 1 if index % 2 == 0 else 3
    metrics = evaluate_trace(
        trace, ["base", "conservative", "stress"],
        json.loads(costs.read_text()), cost_hash,
        json.loads(sizing.read_text()), sizing_hash)
    assert metrics["minimum_actual_notional_usdc"] == 100
    assert metrics["maximum_actual_notional_usdc"] == 200
    assert metrics["minimum_initial_stop_distance_pct"] == 1
    assert metrics["maximum_initial_stop_distance_pct"] == 3
    assert metrics["minimum_notional_pass"] is True


def test_holdout_rejects_trade_notional_below_observed_venue_minimum(tmp_path):
    costs, sizing_path, cost_hash, _ = _sources(tmp_path)
    sizing = json.loads(sizing_path.read_text())
    sizing["position_notional_usdc"] = 5
    sizing_path.write_text(json.dumps(sizing, sort_keys=True) + "\n")
    sizing_hash = hashlib.sha256(sizing_path.read_bytes()).hexdigest()
    trace = _trace(cost_hash, sizing_hash)
    trace["position_notional_usdc"] = 5
    trace_path = tmp_path / "below-minimum.trace.json"
    trace_path.write_text(json.dumps(trace, sort_keys=True) + "\n")
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
        small_account_artifact_path=sizing_path, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "below-minimum.json")
    metric = artifact["candidate_holdout_metrics"]["candidate"]
    assert metric["venue_minimum_notional_usdc"] == 10
    assert metric["minimum_actual_notional_usdc"] == 5
    assert metric["minimum_notional_pass"] is False
    assert artifact["decision"] == "REJECT"


def test_hashed_but_tampered_summary_does_not_pass_recomputation(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    artifact["minimum_holdout_profit_factor"] += 1
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:final_holdout_validation:TRACE_CONTRACT" in errors
    assert "STAGE_ARTIFACT:final_holdout_validation:PROFIT_FACTOR_RECOMPUTES" in errors


def test_holdout_cannot_change_frozen_sizing_or_cost_sources(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    sizing_path = tmp_path / "small-account.json"
    sizing = json.loads(sizing_path.read_text())
    sizing["position_notional_usdc"] = 201
    sizing_path.write_text(json.dumps(sizing))
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "final_holdout_validation", artifact, receipt,
        json.loads((ROOT / "methodology_v4.json").read_text()),
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:final_holdout_validation:FROZEN_SIZING_AND_COSTS" in errors
    assert "STAGE_ARTIFACT:final_holdout_validation:TRACE_CONTRACT" in errors

    costs, sizing_path, cost_hash, sizing_hash = _sources(tmp_path)
    trace = _trace(cost_hash, sizing_hash)
    trace["selected_leverage"] = 8
    trace_path = tmp_path / "changed-sizing.trace.json"
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="Sizing del holdout"):
        build_artifact(
            campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
            small_account_artifact_path=sizing_path, cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "changed-sizing.json")
