import json
from copy import deepcopy
from pathlib import Path

from lab.sq_bridge.e2e_control import generate, payload
from lab.sq_bridge.methodology import validate
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent
METHODOLOGY_PATH = ROOT / "methodology_v4.json"
METHODOLOGY = json.loads(METHODOLOGY_PATH.read_text())


def test_v4_separates_pre_sq_screen_from_strategyquant_generation():
    assert validate(METHODOLOGY) == []
    assert METHODOLOGY["stages"][:3] == [
        "market_preflight", "hypothesis_screen", "sq_generation"]
    assert METHODOLOGY["market_preflight"][
        "minimum_overall_observation_coverage_ratio"] == .9
    assert METHODOLOGY["market_preflight"]["performance_accessed"] is False


def test_v4_market_preflight_cannot_pass_on_mapping_without_history():
    artifact = payload("market_preflight", [], False)
    artifact.update({"campaign_id": "v4", "historical_coverage_pass": False,
                     "historical_overall_coverage_ratio": .42,
                     "historical_minimum_period_coverage_ratio": .02})
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "market_preflight", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:market_preflight:HISTORICAL_COVERAGE_PASS" in errors
    assert "STAGE_ARTIFACT:market_preflight:OVERALL_COVERAGE" in errors
    assert "STAGE_ARTIFACT:market_preflight:PERIOD_COVERAGE" in errors


def test_v4_recomputes_coverage_instead_of_trusting_reported_summary():
    artifact = payload("market_preflight", [], False)
    artifact["campaign_id"] = "v4"
    artifact["historical_overall_coverage_ratio"] = .99
    artifact["historical_minimum_period_coverage_ratio"] = .99
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "market_preflight", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:market_preflight:OVERALL_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:market_preflight:PERIOD_MINIMUM_RECOMPUTES" in errors


def test_v4_screen_must_prove_sample_pf_neighbors_costs_and_sealed_futures():
    artifact = payload("hypothesis_screen", [], False)
    artifact["campaign_id"] = "v4"
    artifact.update({
        "attempted": 5001,
        "minimum_selected_train_trades": 49,
        "minimum_selected_train_profit_factor": 1.19,
        "minimum_selected_stable_neighbors": 1,
        "applied_cost_scenarios": ["base", "conservative"],
        "future_periods_accessed": True,
    })
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    expected = {
        "ATTEMPT_LIMIT", "TRAIN_TRADES", "TRAIN_PF", "STABLE_NEIGHBORS",
        "COST_SET", "FUTURES_SEALED",
    }
    assert expected <= {error.rsplit(":", 1)[-1] for error in errors}


def test_v4_sq_generation_cannot_exceed_frozen_attempt_budget():
    artifact = payload("sq_generation", ["candidate"], False)
    artifact["campaign_id"] = "v4"
    artifact["attempted"] = 10001
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:ATTEMPT_LIMIT" in errors


def test_v4_methodology_cannot_be_weakened_to_force_a_pass():
    weakened = deepcopy(METHODOLOGY)
    weakened["hypothesis_screen"].update({
        "maximum_attempts": 50_000, "minimum_trades_train": 5,
        "minimum_profit_factor_train": 1.01, "minimum_stable_neighbors": 1,
        "cost_scenarios_required": ["base"],
    })
    weakened["sq_generation"].update({"maximum_attempts": 100_000, "max_rules": 20})
    weakened["temporal_validation"].update({
        "minimum_trades_oos": 5, "minimum_positive_windows_ratio": .1,
        "minimum_oos_profit_factor": 1.01, "maximum_oos_drawdown_pct": 80,
    })
    weakened["robustness"].update({
        "monte_carlo_runs": 10, "minimum_profitable_monte_carlo_ratio": .1,
        "cost_stress_multiplier": 1, "maximum_liquidation_probability": .2,
    })
    weakened["small_account"].update({
        "maximum_risk_per_trade_pct": 10, "maximum_portfolio_margin_pct": 100,
        "minimum_reserve_pct": 0, "minimum_net_expectancy_usdc": 0,
        "minimum_net_profit_factor": 1,
    })
    errors = validate(weakened)
    assert len(errors) >= 18
    assert any("pressupost d'intents" in error for error in errors)
    assert any("risc per trade" in error for error in errors)
    assert any("Monte Carlo" in error for error in errors)


def test_v4_full_control_wires_nine_stages_without_becoming_promotable(tmp_path):
    result = generate(METHODOLOGY_PATH, tmp_path)
    assert result["valid"] is True
    assert result["operational_control_complete"] is True
    assert result["paper_ready"] is False
    assert len(list(tmp_path.glob("[0-9][0-9]_*.json"))) == 9
