import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.sq_bridge.small_account_artifact_v4 import (
    build_artifact, evaluate_trace, liquidation_distance_pct,
    select_cost_envelope,
)
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


@pytest.mark.parametrize(("leverage", "expected"), [
    (5, 19.875),
    (10, 9.875),
    (20, 4.875),
    (50, 1.875),
    (100, .875),
    (200, .375),
])
def test_liquidation_distance_matches_official_ostium_examples(
        leverage, expected):
    assert liquidation_distance_pct(leverage, 200) == pytest.approx(expected)


@pytest.mark.parametrize(("leverage", "venue_max"), [
    (0, 200), (-1, 200), (201, 200), (1, 0),
    (float("nan"), 200), (1, float("inf")),
])
def test_liquidation_distance_rejects_invalid_venue_inputs(
        leverage, venue_max):
    with pytest.raises(ValueError, match="liquidacio"):
        liquidation_distance_pct(leverage, venue_max)


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
        "venue_max_leverage": 100, "cost_model_sha256": "",
        "trades": [{"trade_id": f"trade-{index:02d}",
                    "gross_return_pct": win if index < 18 else loss,
                    "side": "long" if index % 2 == 0 else "short",
                    "holding_days": 1}
                   for index in range(30)],
    }


def _cost_model(tmp_path):
    path = tmp_path / "costs.json"
    row = {"base_roundtrip_bps": 0, "conservative_roundtrip_bps": 1,
           "stress_roundtrip_bps": 2}
    carry = {scenario + "_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    path.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"500": row},
        "venue_limits": {"min_notional_usd": {
            "min": 10, "p50": 10, "p95": 10, "max": 10, "n": 30}},
        "carry": {"long": carry, "short": carry}}, sort_keys=True) + "\n")
    return path


def _write(tmp_path, trace, cost_model):
    trace["cost_model_sha256"] = hashlib.sha256(cost_model.read_bytes()).hexdigest()
    path = tmp_path / f"{trace['candidate_id']}.small-account.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_small_account_recomputes_performance_sizing_and_real_contract(tmp_path):
    robustness = _robustness(tmp_path)
    costs = _cost_model(tmp_path)
    trace = _write(tmp_path, _trace(), costs)
    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["selected_leverage"] == 5
    assert artifact["position_notional_usdc"] == 300
    assert artifact["venue_minimum_notional_usdc"] == 10
    assert artifact["cost_notional_bucket_usdc"] == 500
    assert artifact["cost_roundtrip_bps_by_scenario"] == {
        "base": 0, "conservative": 1, "stress": 2}
    assert artifact["collateral_usdc"] == 60
    assert artifact["entry_cost_buffer_usdc"] == pytest.approx(.06)
    assert artifact["capital_committed_usdc"] == pytest.approx(60.06)
    assert artifact["reserve_usdc"] == pytest.approx(139.94)
    assert artifact["reserve_pct"] == pytest.approx(69.97)
    assert artifact["nominal_liquidation_distance_pct"] == pytest.approx(19.75)
    assert artifact["liquidation_cost_erosion_pct"] == pytest.approx(.02)
    assert artifact["liquidation_distance_pct"] == pytest.approx(19.73)
    assert artifact["liquidation_model"] == "ostium_threshold_cost_buffered"
    assert set(artifact["higher_leverage_rejection_reasons"]) == {
        "8", "10", "15", "20", "30", "50", "75", "100"}
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "small_account_economics", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_fixed_oracle_is_not_scaled_down_from_larger_cost_bucket(tmp_path):
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    row = model["by_notional"]["500"]
    row.update({
        "stress_variable_roundtrip_bps": 2,
        "oracle_net_usdc": {"base": 0, "conservative": 0, "stress": .1},
        # 2 variable bps + 2 bucket-equivalent bps for the fixed oracle.
        "stress_roundtrip_bps": 4,
    })
    bucket, variable, fixed, _ = select_cost_envelope(model, 300)
    assert bucket == 500
    assert variable["stress"] == 2
    assert fixed["stress"] == pytest.approx(.1)
    effective_bps = variable["stress"] + fixed["stress"] / 300 * 10_000
    assert effective_bps == pytest.approx(5.333333333333333)
    assert 300 * variable["stress"] / 10_000 + fixed["stress"] == pytest.approx(.16)
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")
    trace = _trace()
    digest = hashlib.sha256(costs.read_bytes()).hexdigest()
    trace["cost_model_sha256"] = digest
    result = evaluate_trace(
        trace, json.loads((ROOT / "methodology_v4.json").read_text())["small_account"],
        {"tested_leverage": 5, "venue_max_leverage": 100}, model, digest)
    assert result["entry_cost_buffer_usdc"] == pytest.approx(.16)
    assert result["cost_fixed_usdc_by_scenario"]["stress"] == pytest.approx(.1)
    assert result["cost_roundtrip_bps_by_scenario"]["stress"] == pytest.approx(
        5.333333333333333)


def test_cost_envelope_cannot_understate_a_noisier_smaller_bucket(tmp_path):
    model = json.loads(_cost_model(tmp_path).read_text())
    smaller = dict(model["by_notional"]["500"])
    smaller["conservative_roundtrip_bps"] = 7
    smaller["stress_roundtrip_bps"] = 11
    smaller["oracle_net_usdc"] = {
        "base": 0, "conservative": 0, "stress": .2}
    smaller["stress_variable_roundtrip_bps"] = 1
    model["by_notional"]["200"] = smaller
    ceiling = model["by_notional"]["500"]
    ceiling["oracle_net_usdc"] = {
        "base": 0, "conservative": 0, "stress": .1}
    ceiling["stress_variable_roundtrip_bps"] = 2
    ceiling["stress_roundtrip_bps"] = 4

    bucket, variable, fixed, _ = select_cost_envelope(model, 300)

    assert bucket == 500
    assert variable == {"base": 0, "conservative": 7, "stress": 2}
    assert fixed == {"base": 0, "conservative": 0, "stress": .2}


def test_dynamic_stops_size_each_trade_and_use_worst_margin_envelope(tmp_path):
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    trace = _trace()
    trace["schema_version"] = 2
    trace.pop("stop_distance_pct")
    for index, trade in enumerate(trace["trades"]):
        trade["initial_stop_distance_pct"] = 1 if index < 15 else 2
        trade["entry_timestamp"] = (
            datetime(1999, 12, 31, tzinfo=timezone.utc) + timedelta(days=index)
        ).isoformat()
        trade["exit_timestamp"] = (
            datetime(2000, 1, 1, tzinfo=timezone.utc) + timedelta(days=index)
        ).isoformat()
    costs = _cost_model(tmp_path)
    digest = hashlib.sha256(costs.read_bytes()).hexdigest()
    trace["cost_model_sha256"] = digest
    result = evaluate_trace(
        trace, methodology["small_account"],
        {"tested_leverage": 5, "venue_max_leverage": 100},
        json.loads(costs.read_text()), digest)
    assert result["minimum_position_notional_usdc"] == 150
    assert result["maximum_position_notional_usdc"] == 300
    assert result["position_notional_usdc"] == 300
    assert result["minimum_stop_distance_pct"] == 1
    assert result["maximum_stop_distance_pct"] == 2
    assert result["collateral_usdc"] == 60
    assert len(result["stress_pnl_by_exit_utc"]) == 30
    assert result["stress_pnl_by_exit_utc"] == sorted(
        result["stress_pnl_by_exit_utc"], key=lambda row: row["exit_timestamp"])
    assert len(result["portfolio_commitment_intervals"]) == 30
    assert result["portfolio_commitment_intervals"][0]["stop_risk_usdc"] == 3


def test_position_below_observed_venue_minimum_is_rejected(tmp_path):
    robustness = _robustness(tmp_path)
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    model["venue_limits"]["min_notional_usd"]["max"] = 350
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, _trace(), costs)],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "below-minimum.json")
    row = artifact["evaluated_candidate_small_account_metrics"]["candidate"]
    assert artifact["decision"] == "REJECT"
    assert row["minimum_notional_pass"] is False
    assert all("position_notional_below_venue_minimum" in value["rejection_reasons"]
               for value in row["leverage_evaluations"].values())


def test_small_account_selects_best_worst_cost_expectancy_deterministically(tmp_path):
    robustness = _robustness(tmp_path, ("a", "b"))
    costs = _cost_model(tmp_path)
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, _trace("a", win=.45), costs),
                     _write(tmp_path, _trace("b", win=.55), costs)],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "selected.json")
    assert artifact["candidate_ids"] == ["b"]
    assert set(artifact["evaluated_candidate_small_account_metrics"]) == {"a", "b"}


def test_artifact_validator_ranks_only_venue_executable_candidates(tmp_path):
    robustness = _robustness(tmp_path, ("a", "b"))
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    model["venue_limits"]["min_notional_usd"].update({
        "min": 200, "p50": 200, "p95": 200, "max": 200})
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")

    # Candidate a has the better expectancy but its 150 USDC notional is
    # below Ostium's observed minimum. Candidate b is worse but executable.
    a = _trace("a", win=.8)
    a["stop_distance_pct"] = 2
    b = _trace("b", win=.5)
    b["stop_distance_pct"] = 1

    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign",
        trace_paths=[_write(tmp_path, a, costs), _write(tmp_path, b, costs)],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=artifact_path)
    assert artifact["evaluated_candidate_small_account_metrics"]["a"][
        "minimum_notional_pass"] is False
    assert artifact["candidate_ids"] == ["b"]
    receipt = {"decision": "PASS", "candidate_ids": ["b"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    assert validate_stage_artifact(
        "small_account_economics", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_small_account_trace_tampering_is_detected(tmp_path):
    robustness = _robustness(tmp_path)
    costs = _cost_model(tmp_path)
    value = _trace()
    trace = _write(tmp_path, value, costs)
    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    value["trades"][0]["gross_return_pct"] = 10
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
    costs = _cost_model(tmp_path)
    trace = _trace(win=3, loss=-.25)
    trace["trades"][-1]["gross_return_pct"] = -3
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, trace, costs)],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []


def test_eurusd_broker_api_cap_prevents_non_executable_leverage_selection(tmp_path):
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    trace = _trace()
    trace["venue_max_leverage"] = 200
    costs = _cost_model(tmp_path)
    trace["cost_model_sha256"] = hashlib.sha256(costs.read_bytes()).hexdigest()
    result = evaluate_trace(trace, methodology["small_account"], {
        "tested_leverage": 100, "venue_max_leverage": 200},
        json.loads(costs.read_text()), trace["cost_model_sha256"])
    assert result["venue_max_leverage"] == 200
    assert result["execution_max_leverage"] == 100
    assert result["evaluated_leverage_grid"][-1] == 100
    assert 150 not in result["evaluated_leverage_grid"]
    assert 200 not in result["evaluated_leverage_grid"]


def test_upfront_stress_cost_consumes_reserve_before_leverage_selection(tmp_path):
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    trace = _trace()
    trace["risk_per_trade_pct"] = 1.0  # 200 USDC notional at a 1% stop
    costs = _cost_model(tmp_path)
    model = json.loads(costs.read_text())
    model["by_notional"]["500"]["stress_roundtrip_bps"] = 1100
    costs.write_text(json.dumps(model, sort_keys=True) + "\n")
    trace["cost_model_sha256"] = hashlib.sha256(costs.read_bytes()).hexdigest()
    result = evaluate_trace(
        trace, methodology["small_account"],
        {"tested_leverage": 2, "venue_max_leverage": 100},
        model, trace["cost_model_sha256"])
    # At 2x collateral alone leaves 50% reserve. The 22 USDC stress entry
    # buffer reduces it to 39%, so the candidate must not select 2x.
    assert result["leverage_evaluations"]["2"]["reserve_pct"] == pytest.approx(39)
    assert "reserve_below_limit" in result["leverage_evaluations"]["2"][
        "rejection_reasons"]
    assert result["selected_leverage"] is None


def test_notional_above_measured_cost_grid_fails_closed(tmp_path):
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    trace = _trace()
    trace["stop_distance_pct"] = .1  # 3,000 USDC > the synthetic 500 bucket.
    costs = _cost_model(tmp_path)
    digest = hashlib.sha256(costs.read_bytes()).hexdigest()
    trace["cost_model_sha256"] = digest
    with pytest.raises(ValueError, match="fora de la graella"):
        evaluate_trace(trace, methodology["small_account"], {
            "tested_leverage": 5, "venue_max_leverage": 100},
            json.loads(costs.read_text()), digest)


def test_cost_model_tampering_invalidates_source_contract(tmp_path):
    robustness, costs = _robustness(tmp_path), _cost_model(tmp_path)
    trace = _write(tmp_path, _trace(), costs)
    artifact_path = tmp_path / "small.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace],
        robustness_artifact_path=robustness, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    costs.write_text("{}\n")
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "small_account_economics", artifact, receipt,
        json.loads((ROOT / "methodology_v4.json").read_text()),
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:small_account_economics:SOURCE_TRACE_CONTRACT" in errors
