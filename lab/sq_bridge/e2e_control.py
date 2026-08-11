#!/usr/bin/env python3
"""Generate a deterministic, non-promotable control for the Alquimia v3 pipeline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.evidence_chain import append_receipt, new_chain, verify


CAMPAIGN = "alquimia-v3-strict-control"
CANDIDATE = "synthetic-sqx-control-001"


def payload(stage: str, candidate_ids: list[str], holdout: bool) -> dict:
    common = {
        "schema_version": 1,
        "stage": stage,
        "campaign_id": CAMPAIGN,
        "decision": "PASS",
        "candidate_ids": candidate_ids,
        "holdout_accessed": holdout,
        "evidence_class": "synthetic_control",
        "control_purpose": "pipeline_wiring_only",
    }
    fields = {
        "market_preflight": {"market_executable": True, "data_gate": "PASS", "ostium_pair_id": "control-pair",
                             "performance_accessed": False, "historical_coverage_pass": True,
                             "historical_expected_observations": 100,
                             "historical_complete_observations": 95,
                             "historical_overall_coverage_ratio": .95,
                             "historical_minimum_period_coverage_ratio": .85,
                             "historical_period_coverage": {"train-a": .85, "train-b": .95},
                             "source_mapping_pass": True, "proxy_candle_coverage_pct": 99,
                             "return_correlation": .999, "execution_economics_complete": True,
                             "future_periods_sealed": True, "campaign_config_sha256": "c" * 64},
        "discovery": {"generator": "StrategyQuant", "attempted": 1, "selected_candidate_ids": candidate_ids},
        "hypothesis_screen": {"generator": "deterministic_pre_sq_screen", "attempted": 1,
                              "selected_hypothesis_ids": ["hypothesis-control"],
                              "minimum_selected_train_trades": 50,
                              "minimum_selected_train_profit_factor": 1.2,
                              "stable_region_pass": True, "all_cost_scenarios_applied": True,
                              "minimum_selected_stable_neighbors": 2,
                              "selected_hypothesis_metrics": {"hypothesis-control": {
                                  "train_trades": 50, "stable_neighbor_count": 2,
                                  "profit_factor_by_cost": {
                                      "base": 1.3, "conservative": 1.25, "stress": 1.2}}},
                              "evaluated_hypothesis_metrics": {"hypothesis-control": {
                                  "train_trades": 50, "stable_neighbor_count": 2,
                                  "profit_factor_by_cost": {
                                      "base": 1.3, "conservative": 1.25, "stress": 1.2},
                                  "central_variant_id": "central", "variant_count": 3,
                                  "central_pass": True}},
                              "applied_cost_scenarios": ["base", "conservative", "stress"],
                              "train_only": True, "future_periods_accessed": False},
        "sq_generation": {"generator": "StrategyQuant", "search_method": "genetic_evolution",
                          "selection_policy": "all_supported_translatable_unique_candidates",
                          "attempted": 1, "source_hypothesis_ids": ["hypothesis-control"],
                          "selected_candidate_ids": candidate_ids,
                          "candidate_artifact_hashes": {candidate: "a" * 64
                                                        for candidate in candidate_ids},
                          "rules_per_candidate": {candidate: 3 for candidate in candidate_ids},
                          "databank_frozen": True, "future_periods_accessed": False,
                          "sq_config_sha256": "b" * 64},
        "temporal_validation": {"oos_trades": 30, "positive_windows_ratio": 0.6, "oos_profit_factor": 1.15,
                                "oos_drawdown_pct": 20, "train_oos_expectancy_decay_pct": 50,
                                "candidate_temporal_metrics": {candidate: {
                                    "oos_trades": 30, "positive_windows_ratio": .6,
                                    "oos_profit_factor": 1.15, "oos_drawdown_pct": 20,
                                    "train_oos_expectancy_decay_pct": 50,
                                    "net_expectancy_usdc": .1}
                                    for candidate in candidate_ids},
                                "evaluated_candidate_temporal_metrics": {candidate: {
                                    "oos_trades": 30, "positive_windows_ratio": .6,
                                    "oos_profit_factor": 1.15, "oos_drawdown_pct": 20,
                                    "train_oos_expectancy_decay_pct": 50,
                                    "net_expectancy_usdc": .1}
                                    for candidate in candidate_ids},
                                "pareto_candidate_ids": candidate_ids,
                                "selection_metric": "pareto_net_expectancy_drawdown_window_stability"},
        "robustness": {"monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": 0.7,
                       "parameter_perturbation_pct": 10, "cost_stress_multiplier": 2,
                       "minimum_parameter_variant_count": 4,
                       "profitable_parameter_variants_ratio": .75,
                       "stress_profit_factor": 1.05, "liquidation_probability": 0.001,
                       "candidate_robustness_metrics": {candidate: {
                           "monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .7,
                           "parameter_variant_count": 4,
                           "profitable_parameter_variants_ratio": .75,
                           "stress_profit_factor": 1.05, "liquidation_probability": .001,
                           "tested_leverage": 5, "venue_max_leverage": 100,
                           "liquidation_distance_pct": 19.75} for candidate in candidate_ids},
                       "evaluated_candidate_robustness_metrics": {candidate: {
                           "monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .7,
                           "parameter_variant_count": 4,
                           "profitable_parameter_variants_ratio": .75,
                           "stress_profit_factor": 1.05, "liquidation_probability": .001,
                           "tested_leverage": 5, "venue_max_leverage": 100,
                           "liquidation_distance_pct": 19.75} for candidate in candidate_ids},
                       "maximum_tested_leverage": 5},
        "small_account_economics": {"capital_usdc": 200, "net_expectancy_usdc": 0.1,
                                    "net_profit_factor": 1.1, "risk_per_trade_pct": 1.5,
                                    "portfolio_margin_pct": 30, "reserve_pct": 70,
                                    "selected_leverage": 5, "venue_max_leverage": 100,
                                    "leverage_selection_policy": "maximum_safe_in_grid_up_to_venue_limit",
                                    "evaluated_leverage_grid": [1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100],
                                    "higher_leverage_rejection_reasons": {
                                        str(value): "synthetic risk constraint"
                                        for value in (8, 10, 15, 20, 30, 50, 75, 100)},
                                    "stop_loss_required": True, "position_notional_usdc": 300,
                                    "collateral_usdc": 60, "stop_distance_pct": 1,
                                    "entry_cost_buffer_usdc": 0,
                                    "capital_committed_usdc": 60,
                                    "capital_committed_pct": 30,
                                    "reserve_usdc": 140,
                                    "liquidation_distance_pct": 19,
                                    "stop_to_liquidation_buffer_ratio": 19,
                                    "liquidation_model": "ostium_threshold_cost_buffered",
                                    "candidate_selection_policy":
                                        "max_worst_cost_expectancy_then_profit_factor_then_candidate_id",
                                    "evaluated_candidate_small_account_metrics": {
                                        candidate: {
                                            "trades": 30,
                                            "profit_factor_by_cost": {
                                                "base": 1.2, "conservative": 1.15,
                                                "stress": 1.1},
                                            "net_expectancy_usdc_by_cost": {
                                                "base": .2, "conservative": .15,
                                                "stress": .1},
                                            "net_profit_factor": 1.1,
                                            "net_expectancy_usdc": .1,
                                            "maximum_single_trade_loss_pct": 1.5,
                                            "risk_per_trade_pct": 1.5,
                                            "stop_distance_pct": 1,
                                            "position_notional_usdc": 300,
                                            "venue_max_leverage": 100,
                                            "robustness_tested_leverage": 5,
                                            "evaluated_leverage_grid": [
                                                1, 2, 3, 5, 8, 10, 15, 20, 30, 50, 75, 100],
                                            "leverage_evaluations": {},
                                            "selected_leverage": 5,
                                            "collateral_usdc": 60,
                                            "entry_cost_buffer_usdc": 0,
                                            "capital_committed_usdc": 60,
                                            "capital_committed_pct": 30,
                                            "reserve_usdc": 140,
                                            "portfolio_margin_pct": 30,
                                            "reserve_pct": 70,
                                            "liquidation_distance_pct": 19,
                                            "stop_to_liquidation_buffer_ratio": 19,
                                            "higher_leverage_rejection_reasons": {
                                                str(value): "synthetic risk constraint"
                                                for value in (8, 10, 15, 20, 30, 50, 75, 100)},
                                        } for candidate in candidate_ids}},
        "final_holdout_validation": {
            "selection_frozen_before_holdout": True, "holdout_evaluation_count": 1,
            "parameters_changed_after_holdout": False,
            "candidate_holdout_metrics": {candidate: {
                "trades": 20, "drawdown_pct": 20,
                "profit_factor_by_cost": {
                    "base": 1.2, "conservative": 1.15, "stress": 1.1},
                "net_expectancy_usdc_by_cost": {
                    "base": .2, "conservative": .15, "stress": .1},
            } for candidate in candidate_ids},
            "holdout_trades": 20, "minimum_holdout_profit_factor": 1.1,
            "holdout_drawdown_pct": 20, "minimum_holdout_net_expectancy_usdc": .1,
            "applied_cost_scenarios": ["base", "conservative", "stress"]},
        "python_translation": {"translation_exact": True, "supported_subset": True,
                               "trade_execution_normalized": True,
                               "stop_loss_required_satisfied": True,
                               "sqx_sha256": "a" * 64, "canonical_ir_sha256": "b" * 64},
        "parity": {"parity_pass": True, "signal_match_rate": 1.0, "trade_match_rate": 1.0,
                   "candle_coverage_pct": 95, "pnl_correlation": 0.99},
        "paper": {"mode": "paper", "paper_probe_configured": True, "live_authorized": False},
    }
    common.update(fields[stage])
    return common


def generate(methodology_path: Path, output_dir: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    chain = new_chain(methodology_path, CAMPAIGN, "wiring-control", "SYNTHETIC", "synthetic_control")
    ids: list[str] = []
    for index, stage in enumerate(methodology["stages"], 1):
        if stage in {"discovery", "sq_generation"}:
            ids = [CANDIDATE]
        holdout = stage == "final_holdout_validation"
        stage_payload = payload(stage, ids, holdout)
        if stage == "sq_generation":
            paths, hashes = {}, {}
            for candidate in ids:
                candidate_path = output_dir / f"{candidate}.sqx"
                candidate_path.write_bytes(f"synthetic-control:{candidate}".encode())
                paths[candidate] = candidate_path.name
                hashes[candidate] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
            stage_payload["candidate_artifact_paths"] = paths
            stage_payload["candidate_artifact_hashes"] = hashes
            manifest_path = output_dir / "synthetic-project.manifest.json"
            manifest_path.write_text(json.dumps({
                "schema_version": 1, "methodology_id": methodology["methodology_id"],
                "generation_type": "genetic-evolution", "attempt_budget": 100,
                "attempt_stop_guard": methodology["sq_generation"]["attempt_stop_guard"],
                "accepted_limit": methodology["sq_generation"][
                    "accepted_candidates_per_branch"],
                "output_sha256": "b" * 64, "canonical_evaluation_capital": 200,
                "sq_discovery_spread": 0, "sq_discovery_commission": 0,
                "sq_discovery_slippage": 0,
                "venue_cost_application_stage": "post_sq_frozen_cost_model",
                "holdout_sealed": True, "source_role": "xml_format_scaffold_only",
            }, sort_keys=True) + "\n")
            stage_payload["sq_project_manifest_path"] = manifest_path.name
            stage_payload["sq_project_manifest_sha256"] = hashlib.sha256(
                manifest_path.read_bytes()).hexdigest()
        if stage == "python_translation":
            sqx_path = output_dir / f"{CANDIDATE}.sqx"
            ir_path = output_dir / f"{CANDIDATE}.ir.json"
            if not sqx_path.exists():
                sqx_path.write_bytes(f"synthetic-control:{CANDIDATE}".encode())
            ir_path.write_text('{"synthetic_control":true}\n')
            stage_payload.update({
                "sqx_path": sqx_path.name,
                "sqx_sha256": hashlib.sha256(sqx_path.read_bytes()).hexdigest(),
                "canonical_ir_path": ir_path.name,
                "canonical_ir_sha256": hashlib.sha256(ir_path.read_bytes()).hexdigest(),
            })
        if stage == "parity":
            report_path = output_dir / f"{CANDIDATE}.parity.json"
            report_path.write_text(json.dumps({
                "schema_version": 1, "candidate_id": CANDIDATE,
                "signal_match_rate": 1.0, "trade_match_rate": 1.0,
                "candle_coverage_pct": 95, "pnl_correlation": .99,
            }, sort_keys=True) + "\n")
            stage_payload.update({
                "parity_report_path": report_path.name,
                "parity_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            })
        if stage == "paper":
            config_path = output_dir / f"{CANDIDATE}.paper.json"
            config_path.write_text(json.dumps({
                "schema_version": 1, "candidate_id": CANDIDATE, "capital_usdc": 200,
                "mode": "paper", "live_authorized": False, "signer_enabled": False,
            }, sort_keys=True) + "\n")
            stage_payload.update({
                "paper_config_path": config_path.name,
                "paper_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            })
        artifact = output_dir / f"{index:02d}_{stage}.json"
        artifact.write_text(json.dumps(stage_payload, indent=2, sort_keys=True) + "\n")
        chain = append_receipt(
            chain, methodology, stage, artifact, "PASS", ids,
            holdout_accessed=holdout,
            translation_exact=True if stage == "python_translation" else None,
            parity_pass=True if stage == "parity" else None,
        )
    chain_path = output_dir / "chain.json"
    chain_path.write_text(json.dumps(chain, indent=2, sort_keys=True) + "\n")
    result = verify(chain, methodology_path)
    verification_path = output_dir / "verification.json"
    verification_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not (result["valid"] and result["operational_control_complete"]):
        raise RuntimeError(f"control failed: {result['errors']}")
    if result["promotable"] or result["paper_ready"] or result["live_authorized"]:
        raise RuntimeError("synthetic control escaped its non-promotable boundary")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v3.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.methodology, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
