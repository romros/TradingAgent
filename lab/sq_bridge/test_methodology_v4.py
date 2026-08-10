import json
import hashlib
import zipfile
from copy import deepcopy
from pathlib import Path

from lab.sq_bridge.e2e_control import generate, payload
from lab.sq_bridge.evidence_chain import append_receipt, new_chain, verify
from lab.sq_bridge.methodology import validate
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.sqx_to_ir import translate
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY


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
    assert METHODOLOGY["hypothesis_screen"]["screen_notional_usdc"] == 200
    assert METHODOLOGY["temporal_validation"]["evaluation_notional_usdc"] == 200
    assert METHODOLOGY["robustness"]["evaluation_notional_usdc"] == 200


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


def test_v4_screen_recomputes_worst_selected_hypothesis_metrics():
    artifact = payload("hypothesis_screen", [], False)
    artifact.update({"campaign_id": "v4", "evidence_class": "observed"})
    artifact.pop("control_purpose", None)
    artifact["selected_hypothesis_ids"] = ["h1", "h2"]
    artifact["selected_hypothesis_metrics"] = {
        "h1": {"train_trades": 80, "stable_neighbor_count": 3,
               "profit_factor_by_cost": {"base": 1.5, "conservative": 1.35, "stress": 1.25}},
        "h2": {"train_trades": 60, "stable_neighbor_count": 2,
               "profit_factor_by_cost": {"base": 1.4, "conservative": 1.3, "stress": 1.2}},
    }
    artifact.update({"minimum_selected_train_trades": 80,
                     "minimum_selected_train_profit_factor": 1.25,
                     "minimum_selected_stable_neighbors": 3})
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:hypothesis_screen:TRAIN_TRADES_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:hypothesis_screen:TRAIN_PF_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:hypothesis_screen:STABLE_NEIGHBORS_RECOMPUTES" in errors


def test_v4_sq_generation_cannot_exceed_frozen_attempt_budget():
    artifact = payload("sq_generation", ["candidate"], False)
    artifact["campaign_id"] = "v4"
    artifact["attempted"] = 10001
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:ATTEMPT_LIMIT" in errors


def test_v4_sq_generation_requires_genetic_search_and_rule_limit():
    artifact = payload("sq_generation", ["candidate"], False)
    artifact["campaign_id"] = "v4"
    artifact["search_method"] = "random_search"
    artifact["rules_per_candidate"]["candidate"] = 4
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, METHODOLOGY, "v4", "synthetic_control")
    assert "STAGE_ARTIFACT:sq_generation:SEARCH_METHOD" in errors
    assert "STAGE_ARTIFACT:sq_generation:RULE_COUNTS" in errors


def test_v4_recomputes_sq_and_translation_file_hashes(tmp_path):
    sqx = tmp_path / "candidate.sqx"
    settings = SETTINGS.replace(b'>T</StrategyName>', b'>candidate</StrategyName>')
    with zipfile.ZipFile(sqx, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr("settings.xml", settings)
        archive.writestr("version.txt", "3")
    generation = payload("sq_generation", ["candidate"], False)
    generation.update({"campaign_id": "v4", "evidence_class": "observed",
                       "candidate_artifact_paths": {"candidate": sqx.name}})
    generation.pop("control_purpose", None)
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(tmp_path / "generation.json")}
    errors = validate_stage_artifact(
        "sq_generation", generation, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:ARTIFACT_FILES" in errors

    generation["candidate_artifact_hashes"] = {
        "candidate": hashlib.sha256(sqx.read_bytes()).hexdigest()}
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "methodology_id": METHODOLOGY["methodology_id"],
        "generation_type": "random-generation", "attempt_budget": 1,
            "output_sha256": "b" * 64, "canonical_evaluation_capital": 200,
            "sq_discovery_spread": 0, "sq_discovery_commission": 0,
            "sq_discovery_slippage": 0,
            "venue_cost_application_stage": "post_sq_frozen_cost_model",
        "holdout_sealed": True, "source_role": "xml_format_scaffold_only"}))
    generation.update({
        "sq_project_manifest_path": manifest.name,
        "sq_project_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()})
    errors = validate_stage_artifact(
        "sq_generation", generation, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:PROJECT_MANIFEST_CONTRACT" in errors

    ir = tmp_path / "candidate.ir.json"
    translate(sqx, ir)
    translation = payload("python_translation", ["candidate"], False)
    translation.update({
        "campaign_id": "v4", "evidence_class": "observed",
        "trade_execution_normalized": True,
        "stop_loss_required_satisfied": True,
        "sqx_path": sqx.name, "sqx_sha256": hashlib.sha256(sqx.read_bytes()).hexdigest(),
        "canonical_ir_path": ir.name,
        "canonical_ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest(),
        "execution_contract": {
            "active_directions": ["long", "short"],
            "stop_loss_required": True,
            "stop_loss_present_all_directions": True,
            "timed_session_exits_disabled": True,
            "sq_venue_costs_disabled": True,
            "causal_entry_signals": True,
            "minimum_market_data_shift": None,
        },
    })
    translation.pop("control_purpose", None)
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(tmp_path / "translation.json"),
               "translation_exact": True}
    assert validate_stage_artifact(
        "python_translation", translation, receipt, METHODOLOGY,
        "v4", "alquimia_native") == []
    ir.write_text('{"tampered":true}')
    errors = validate_stage_artifact(
        "python_translation", translation, receipt, METHODOLOGY,
        "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:python_translation:IR_FILE" in errors


def test_v4_parity_and_paper_verify_hashed_json_contents(tmp_path):
    parity_report = tmp_path / "parity.json"
    parity_report.write_text(json.dumps({
        "schema_version": 1, "candidate_id": "wrong",
        "signal_match_rate": 1.0, "trade_match_rate": 1.0,
        "candle_coverage_pct": 95, "pnl_correlation": .99}))
    parity = payload("parity", ["candidate"], True)
    parity.update({
        "campaign_id": "v4", "evidence_class": "observed",
        "parity_report_path": parity_report.name,
        "parity_report_sha256": hashlib.sha256(parity_report.read_bytes()).hexdigest(),
    })
    parity.pop("control_purpose", None)
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(tmp_path / "parity-stage.json"),
               "parity_pass": True}
    errors = validate_stage_artifact(
        "parity", parity, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:parity:REPORT_CONTRACT" in errors

    paper_config = tmp_path / "paper.json"
    paper_config.write_text(json.dumps({
        "schema_version": 1, "candidate_id": "candidate", "capital_usdc": 200,
        "mode": "paper", "live_authorized": False, "signer_enabled": True}))
    paper = payload("paper", ["candidate"], True)
    paper.update({
        "campaign_id": "v4", "evidence_class": "observed",
        "paper_config_path": paper_config.name,
        "paper_config_sha256": hashlib.sha256(paper_config.read_bytes()).hexdigest(),
    })
    paper.pop("control_purpose", None)
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(tmp_path / "paper-stage.json")}
    errors = validate_stage_artifact(
        "paper", paper, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:paper:CONFIG_CONTRACT" in errors


def test_v4_chain_rejects_sq_candidates_from_an_unscreened_hypothesis(tmp_path):
    chain = new_chain(METHODOLOGY_PATH, "lineage", "approved", "US500")
    specifications = [
        ("market_preflight", [], {}),
        ("hypothesis_screen", [], {"selected_hypothesis_ids": ["approved"]}),
        ("sq_generation", ["candidate"], {"source_hypothesis_ids": ["different"]}),
    ]
    for index, (stage, ids, changes) in enumerate(specifications):
        artifact = payload(stage, ids, False)
        artifact.update({"campaign_id": "lineage", "evidence_class": "observed", **changes})
        artifact.pop("control_purpose", None)
        path = tmp_path / f"{index}_{stage}.json"
        path.write_text(json.dumps(artifact))
        chain = append_receipt(chain, METHODOLOGY, stage, path, "PASS", ids)
    assert "SQ_HYPOTHESIS_LINEAGE" in verify(chain, METHODOLOGY_PATH)["errors"]


def test_v4_methodology_cannot_be_weakened_to_force_a_pass():
    weakened = deepcopy(METHODOLOGY)
    weakened["hypothesis_screen"].update({
        "maximum_attempts": 50_000, "minimum_trades_train": 5,
        "minimum_profit_factor_train": 1.01, "minimum_stable_neighbors": 1,
        "cost_scenarios_required": ["base"],
    })
    weakened["sq_generation"].update({
        "maximum_attempts": 100_000, "attempt_stop_guard": 1, "max_rules": 20,
        "selection_policy": "pick_best_is_fitness"})
    weakened["temporal_validation"].update({
        "minimum_trades_oos": 5, "minimum_positive_windows_ratio": .1,
        "minimum_oos_profit_factor": 1.01, "maximum_oos_drawdown_pct": 80,
        "selection_metric": "best_profit_only",
    })
    weakened["robustness"].update({
        "monte_carlo_runs": 10, "minimum_profitable_monte_carlo_ratio": .1,
        "parameter_perturbation_pct": 1, "minimum_parameter_variants": 1,
        "minimum_profitable_parameter_variants_ratio": .1,
        "cost_stress_multiplier": 1, "maximum_liquidation_probability": .2,
        "liquidation_model": "ostium_nominal_only",
    })
    weakened["small_account"].update({
        "maximum_risk_per_trade_pct": 10, "maximum_portfolio_margin_pct": 100,
        "minimum_reserve_pct": 0, "minimum_net_expectancy_usdc": 0,
        "minimum_net_profit_factor": 1, "minimum_trades": 1,
        "cost_scenarios_required": ["base"],
        "maximum_single_trade_loss_pct": 100,
        "candidate_selection_policy": "best_backtest_profit",
        "liquidation_model": "ostium_nominal_only",
    })
    weakened["parity"].update({
        "minimum_matched_signals": 1, "minimum_matched_trades": 1,
        "minimum_signal_match_rate": .9, "minimum_trade_match_rate": .9,
        "minimum_candle_coverage_pct": 50, "minimum_pnl_correlation": .5,
        "maximum_pnl_mean_absolute_error_usdc": 1,
        "maximum_pnl_absolute_error_usdc": 5,
    })
    weakened["final_holdout_validation"].update({
        "minimum_trades": 1, "minimum_profit_factor": 1.01,
        "maximum_drawdown_pct": 80, "minimum_net_expectancy_usdc": 0,
        "cost_scenarios_required": ["base"], "maximum_evaluations": 5,
    })
    errors = validate(weakened)
    assert len(errors) >= 18
    assert any("pressupost d'intents" in error for error in errors)
    assert any("risc per trade" in error for error in errors)
    assert any("Monte Carlo" in error for error in errors)
    assert sum(error.startswith("parity:") for error in errors) == 8
    assert sum(error.startswith("final_holdout:") for error in errors) == 6


def test_v4_small_account_proves_maximum_safe_leverage_and_recomputes_risk():
    artifact = payload("small_account_economics", ["candidate"], False)
    artifact["campaign_id"] = "v4"
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False}
    assert validate_stage_artifact(
        "small_account_economics", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control") == []
    del artifact["higher_leverage_rejection_reasons"]["100"]
    artifact["portfolio_margin_pct"] = 20
    artifact["reserve_pct"] = 60
    errors = validate_stage_artifact(
        "small_account_economics", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control")
    assert "STAGE_ARTIFACT:small_account_economics:MAXIMUM_SAFE" in errors
    assert "STAGE_ARTIFACT:small_account_economics:MARGIN_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:small_account_economics:RESERVE_RECOMPUTES" in errors


def test_v4_small_account_malformed_sizing_fails_closed_without_crashing():
    artifact = payload("small_account_economics", ["candidate"], False)
    artifact["campaign_id"] = "v4"
    artifact["evidence_class"] = "observed"
    artifact.pop("control_purpose", None)
    artifact.update({"selected_leverage": "100x", "venue_max_leverage": "100",
                     "position_notional_usdc": "all", "collateral_usdc": None})
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False}
    errors = validate_stage_artifact(
        "small_account_economics", artifact, receipt, METHODOLOGY,
        "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:small_account_economics:LEVERAGE" in errors
    assert "STAGE_ARTIFACT:small_account_economics:COLLATERAL_RECOMPUTES" in errors


def test_v4_small_account_cannot_exceed_leverage_tested_in_robustness(tmp_path):
    campaign = "leverage-lineage"
    chain = new_chain(
        METHODOLOGY_PATH, campaign, "hypothesis", "SYNTHETIC", "synthetic_control")
    for stage in METHODOLOGY["stages"][:6]:
        ids = ["candidate"] if stage in {
            "sq_generation", "temporal_validation", "robustness",
            "small_account_economics"} else []
        artifact = payload(stage, ids, False)
        artifact["campaign_id"] = campaign
        if stage == "small_account_economics":
            artifact.update({
                "selected_leverage": 8, "collateral_usdc": 37.5,
                "portfolio_margin_pct": 18.75, "reserve_pct": 81.25,
                "higher_leverage_rejection_reasons": {
                    str(value): "synthetic risk constraint"
                    for value in (10, 15, 20, 30, 50, 75, 100)},
            })
        path = tmp_path / f"{stage}.json"
        path.write_text(json.dumps(artifact))
        chain = append_receipt(
            chain, METHODOLOGY, stage, path, "PASS", ids,
            holdout_accessed=False)
    result = verify(chain, METHODOLOGY_PATH)
    assert "SMALL_ACCOUNT_EXCEEDS_ROBUSTNESS_LEVERAGE" in result["errors"]


def test_v4_temporal_and_robustness_aggregates_must_equal_worst_candidate():
    receipt = {"decision": "PASS", "candidate_ids": ["a", "b"],
               "holdout_accessed": False}
    temporal = payload("temporal_validation", ["a", "b"], False)
    temporal.update({"campaign_id": "v4", "evidence_class": "observed"})
    temporal.pop("control_purpose", None)
    temporal["candidate_temporal_metrics"] = {
        "a": {"oos_trades": 40, "positive_windows_ratio": .7,
              "oos_profit_factor": 1.3, "oos_drawdown_pct": 12,
              "train_oos_expectancy_decay_pct": 30},
        "b": {"oos_trades": 30, "positive_windows_ratio": .6,
              "oos_profit_factor": 1.15, "oos_drawdown_pct": 20,
              "train_oos_expectancy_decay_pct": 50},
    }
    temporal["oos_trades"] = 40
    errors = validate_stage_artifact(
        "temporal_validation", temporal, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:temporal_validation:OOS_TRADES_RECOMPUTES" in errors

    robust = payload("robustness", ["a", "b"], False)
    robust.update({"campaign_id": "v4", "evidence_class": "observed"})
    robust.pop("control_purpose", None)
    robust["candidate_robustness_metrics"] = {
        "a": {"monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .8,
              "stress_profit_factor": 1.2, "liquidation_probability": 0},
        "b": {"monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .7,
              "stress_profit_factor": 1.05, "liquidation_probability": .001},
    }
    robust["stress_profit_factor"] = 1.2
    errors = validate_stage_artifact(
        "robustness", robust, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:robustness:STRESS_PF_RECOMPUTES" in errors


def test_v4_temporal_selection_recomputes_pareto_and_rejects_dominated_candidate():
    evaluated = {
        "a": {"oos_trades": 40, "positive_windows_ratio": .7,
              "oos_profit_factor": 1.3, "oos_drawdown_pct": 10,
              "train_oos_expectancy_decay_pct": 30,
              "net_expectancy_usdc": .2},
        "b": {"oos_trades": 35, "positive_windows_ratio": .6,
              "oos_profit_factor": 1.2, "oos_drawdown_pct": 15,
              "train_oos_expectancy_decay_pct": 40,
              "net_expectancy_usdc": .1},
        "c": {"oos_trades": 30, "positive_windows_ratio": .6,
              "oos_profit_factor": 1.15, "oos_drawdown_pct": 8,
              "train_oos_expectancy_decay_pct": 50,
              "net_expectancy_usdc": .3},
    }
    artifact = payload("temporal_validation", ["a", "c"], False)
    artifact.update({
        "campaign_id": "v4",
        "evaluated_candidate_temporal_metrics": evaluated,
        "candidate_temporal_metrics": {key: evaluated[key] for key in ("a", "c")},
        "pareto_candidate_ids": ["a", "c"],
        "oos_trades": 30, "positive_windows_ratio": .6,
        "oos_profit_factor": 1.15, "oos_drawdown_pct": 10,
        "train_oos_expectancy_decay_pct": 50,
    })
    receipt = {"decision": "PASS", "candidate_ids": ["a", "c"],
               "holdout_accessed": False}
    assert validate_stage_artifact(
        "temporal_validation", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control") == []

    artifact["candidate_temporal_metrics"] = {"b": evaluated["b"]}
    artifact["pareto_candidate_ids"] = ["b"]
    receipt["candidate_ids"] = ["b"]
    errors = validate_stage_artifact(
        "temporal_validation", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control")
    assert "STAGE_ARTIFACT:temporal_validation:PARETO_RECOMPUTES" in errors


def test_v4_full_control_wires_ten_stages_without_becoming_promotable(tmp_path):
    result = generate(METHODOLOGY_PATH, tmp_path)
    assert result["valid"] is True
    assert result["operational_control_complete"] is True
    assert result["paper_ready"] is False
    assert len(list(tmp_path.glob("[0-9][0-9]_*.json"))) == 10


def test_v4_final_holdout_is_single_frozen_evaluation_with_recomputed_worst_cost():
    artifact = payload("final_holdout_validation", ["candidate"], True)
    artifact.update({"campaign_id": "v4"})
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True}
    assert validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control") == []
    artifact["minimum_holdout_profit_factor"] = 1.2
    artifact["parameters_changed_after_holdout"] = True
    artifact["holdout_evaluation_count"] = 2
    errors = validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, METHODOLOGY,
        "v4", "synthetic_control")
    assert "STAGE_ARTIFACT:final_holdout_validation:PROFIT_FACTOR_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:final_holdout_validation:NO_RETUNING" in errors
    assert "STAGE_ARTIFACT:final_holdout_validation:ONE_EVALUATION" in errors
