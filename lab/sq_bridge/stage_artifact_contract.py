#!/usr/bin/env python3
"""Strict, deterministic contracts for Alquimia v3 stage evidence artifacts."""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path
from typing import Any


def _number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _at_least(value: Any, threshold: float) -> bool:
    return _number(value) and value >= threshold


def _at_most(value: Any, threshold: float) -> bool:
    return _number(value) and value <= threshold


def _between(value: Any, minimum: float, maximum: float) -> bool:
    return _number(value) and minimum <= value <= maximum


def _ids(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return sorted(set(value))


def _verified_files(paths: Any, hashes: Any, expected_ids: list[str], artifact_path: str) -> bool:
    if (not isinstance(paths, dict) or not isinstance(hashes, dict)
            or set(paths) != set(expected_ids) or set(hashes) != set(expected_ids)):
        return False
    base = Path(artifact_path).resolve().parent
    for candidate_id in expected_ids:
        value = paths.get(candidate_id)
        digest = hashes.get(candidate_id)
        if not isinstance(value, str) or not value or not isinstance(digest, str):
            return False
        path = Path(value)
        path = path if path.is_absolute() else base / path
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def _verified_json(path_value: Any, digest: Any, artifact_path: str) -> dict | None:
    if not isinstance(path_value, str) or not path_value or not isinstance(digest, str):
        return None
    path = Path(path_value)
    path = path if path.is_absolute() else Path(artifact_path).resolve().parent / path
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def validate_stage_artifact(stage: str, artifact: dict, receipt: dict, methodology: dict,
                            campaign_id: str, provenance: str) -> list[str]:
    errors: list[str] = []
    prefix = f"STAGE_ARTIFACT:{stage}"
    if artifact.get("schema_version") != 1:
        errors.append(f"{prefix}:SCHEMA_VERSION")
    if artifact.get("stage") != stage:
        errors.append(f"{prefix}:STAGE")
    if artifact.get("campaign_id") != campaign_id:
        errors.append(f"{prefix}:CAMPAIGN")
    if artifact.get("decision") != receipt.get("decision"):
        errors.append(f"{prefix}:DECISION")
    artifact_ids = _ids(artifact.get("candidate_ids"))
    if artifact_ids is None or artifact_ids != receipt.get("candidate_ids", []):
        errors.append(f"{prefix}:CANDIDATES")
    if bool(artifact.get("holdout_accessed", False)) != bool(receipt.get("holdout_accessed", False)):
        errors.append(f"{prefix}:HOLDOUT")
    expected_class = "synthetic_control" if provenance == "synthetic_control" else "observed"
    if artifact.get("evidence_class") != expected_class:
        errors.append(f"{prefix}:EVIDENCE_CLASS")
    if provenance == "synthetic_control" and artifact.get("control_purpose") != "pipeline_wiring_only":
        errors.append(f"{prefix}:CONTROL_PURPOSE")
    if receipt.get("decision") != "PASS":
        return errors

    temporal = methodology["temporal_validation"]
    robust = methodology["robustness"]
    small = methodology["small_account"]
    checks: dict[str, bool]
    if stage == "market_preflight":
        checks = {
            "MARKET_EXECUTABLE": artifact.get("market_executable") is True,
            "DATA_GATE": artifact.get("data_gate") == "PASS",
            "OSTIUM_PAIR": bool(artifact.get("ostium_pair_id")),
        }
        if methodology.get("schema_version", 1) >= 4:
            preflight = methodology["market_preflight"]
            expected = artifact.get("historical_expected_observations")
            complete = artifact.get("historical_complete_observations")
            reported_overall = artifact.get("historical_overall_coverage_ratio")
            computed_overall = (complete / expected if _at_least(expected, 1)
                                and _at_least(complete, 0) and complete <= expected else None)
            periods = artifact.get("historical_period_coverage")
            valid_periods = (isinstance(periods, dict) and bool(periods)
                             and all(isinstance(value, (int, float))
                                     and not isinstance(value, bool) and 0 <= value <= 1
                                     for value in periods.values()))
            computed_minimum = min(periods.values()) if valid_periods else None
            checks.update({
                "NO_PERFORMANCE": artifact.get("performance_accessed") is False,
                "HISTORICAL_COVERAGE_PASS": artifact.get("historical_coverage_pass") is True,
                "OVERALL_COVERAGE": _at_least(
                    reported_overall,
                    preflight["minimum_overall_observation_coverage_ratio"]),
                "OVERALL_COUNTS": computed_overall is not None,
                "OVERALL_RECOMPUTES": computed_overall is not None and _at_least(reported_overall, 0)
                                      and abs(reported_overall - computed_overall) <= 1e-12,
                "PERIOD_COVERAGE": _at_least(
                    artifact.get("historical_minimum_period_coverage_ratio"),
                    preflight["minimum_each_period_coverage_ratio"]),
                "PERIODS_PRESENT": valid_periods,
                "PERIOD_MINIMUM_RECOMPUTES": computed_minimum is not None
                    and _at_least(artifact.get("historical_minimum_period_coverage_ratio"), 0)
                    and abs(artifact.get("historical_minimum_period_coverage_ratio")
                            - computed_minimum) <= 1e-12,
                "SOURCE_MAPPING": artifact.get("source_mapping_pass") is True,
                "PROXY_COVERAGE": _at_least(
                    artifact.get("proxy_candle_coverage_pct"),
                    preflight["minimum_proxy_candle_coverage_pct"]),
                "RETURN_CORRELATION": _at_least(
                    artifact.get("return_correlation"),
                    preflight["minimum_return_correlation"]),
                "ECONOMICS": artifact.get("execution_economics_complete") is True,
                "FUTURES_SEALED": artifact.get("future_periods_sealed") is True,
                "CONFIG_HASH": isinstance(artifact.get("campaign_config_sha256"), str)
                               and len(artifact["campaign_config_sha256"]) == 64,
            })
    elif stage == "discovery":
        checks = {
            "SQ_SOURCE": artifact.get("generator") == "StrategyQuant",
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "SELECTED": _ids(artifact.get("selected_candidate_ids")) == receipt.get("candidate_ids", []),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "hypothesis_screen":
        screen = methodology["hypothesis_screen"]
        applied_costs = artifact.get("applied_cost_scenarios")
        selected_hypotheses = _ids(artifact.get("selected_hypothesis_ids"))
        hypothesis_metrics = artifact.get("selected_hypothesis_metrics")
        metrics_valid = (selected_hypotheses is not None and bool(selected_hypotheses)
                         and isinstance(hypothesis_metrics, dict)
                         and set(hypothesis_metrics) == set(selected_hypotheses))
        metric_trades: list[float] = []
        metric_profit_factors: list[float] = []
        metric_neighbors: list[float] = []
        if metrics_valid:
            for metric in hypothesis_metrics.values():
                if not isinstance(metric, dict):
                    metrics_valid = False
                    break
                costs = metric.get("profit_factor_by_cost")
                if (not isinstance(costs, dict)
                        or set(costs) != set(screen["cost_scenarios_required"])
                        or any(not _at_least(value, 0) for value in costs.values())
                        or not _at_least(metric.get("train_trades"), 0)
                        or not _at_least(metric.get("stable_neighbor_count"), 0)):
                    metrics_valid = False
                    break
                metric_trades.append(metric["train_trades"])
                metric_profit_factors.extend(costs.values())
                metric_neighbors.append(metric["stable_neighbor_count"])
        computed_min_trades = min(metric_trades) if metrics_valid else None
        computed_min_pf = min(metric_profit_factors) if metrics_valid else None
        computed_min_neighbors = min(metric_neighbors) if metrics_valid else None
        checks = {
            "GENERATOR": artifact.get("generator") == "deterministic_pre_sq_screen",
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "ATTEMPT_LIMIT": _at_most(
                artifact.get("attempted"), screen["maximum_attempts"]),
            "HYPOTHESES": bool(selected_hypotheses),
            "HYPOTHESIS_METRICS": metrics_valid,
            "TRAIN_TRADES": _at_least(
                artifact.get("minimum_selected_train_trades"),
                screen["minimum_trades_train"]),
            "TRAIN_TRADES_RECOMPUTES": computed_min_trades is not None
                and artifact.get("minimum_selected_train_trades") == computed_min_trades,
            "TRAIN_PF": _at_least(
                artifact.get("minimum_selected_train_profit_factor"),
                screen["minimum_profit_factor_train"]),
            "TRAIN_PF_RECOMPUTES": computed_min_pf is not None
                and artifact.get("minimum_selected_train_profit_factor") == computed_min_pf,
            "STABLE_REGION": artifact.get("stable_region_pass") is True,
            "STABLE_NEIGHBORS": _at_least(
                artifact.get("minimum_selected_stable_neighbors"),
                screen["minimum_stable_neighbors"]),
            "STABLE_NEIGHBORS_RECOMPUTES": computed_min_neighbors is not None
                and artifact.get("minimum_selected_stable_neighbors") == computed_min_neighbors,
            "COSTS": artifact.get("all_cost_scenarios_applied") is True,
            "COST_SET": isinstance(applied_costs, list)
                and set(applied_costs) == set(screen["cost_scenarios_required"]),
            "TRAIN_ONLY": artifact.get("train_only") is True,
            "FUTURES_SEALED": artifact.get("future_periods_accessed") is False,
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "sq_generation":
        generation = methodology["sq_generation"]
        hashes = artifact.get("candidate_artifact_hashes")
        paths = artifact.get("candidate_artifact_paths")
        rules = artifact.get("rules_per_candidate")
        candidate_ids = receipt.get("candidate_ids", [])
        project_manifest = _verified_json(
            artifact.get("sq_project_manifest_path"),
            artifact.get("sq_project_manifest_sha256"), receipt.get("artifact", ""))
        checks = {
            "SQ_SOURCE": artifact.get("generator") == "StrategyQuant",
            "SEARCH_METHOD": artifact.get("search_method") == generation["search_method"],
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "ATTEMPT_LIMIT": _at_most(
                artifact.get("attempted"), generation["maximum_attempts"]),
            "SELECTED": _ids(artifact.get("selected_candidate_ids")) == receipt.get("candidate_ids", []),
            "SOURCE_HYPOTHESES": bool(_ids(artifact.get("source_hypothesis_ids"))),
            "ARTIFACT_HASHES": isinstance(hashes, dict) and bool(hashes)
                               and set(hashes) == set(candidate_ids)
                               and all(isinstance(value, str) and len(value) == 64
                                       for value in hashes.values()),
            "ARTIFACT_FILES": _verified_files(
                paths, hashes, candidate_ids, receipt.get("artifact", "")),
            "RULE_COUNTS": isinstance(rules, dict) and bool(rules)
                and set(rules) == set(receipt.get("candidate_ids", []))
                and all(isinstance(value, int) and not isinstance(value, bool)
                        and 1 <= value <= generation["max_rules"] for value in rules.values()),
            "CONFIG_HASH": isinstance(artifact.get("sq_config_sha256"), str)
                           and len(artifact["sq_config_sha256"]) == 64,
            "PROJECT_MANIFEST_FILE": project_manifest is not None,
            "PROJECT_MANIFEST_CONTRACT": project_manifest is not None
                and project_manifest.get("schema_version") == 1
                and project_manifest.get("methodology_id") == methodology["methodology_id"]
                and project_manifest.get("generation_type")
                    == generation["search_method"].replace("_", "-")
                and isinstance(project_manifest.get("attempt_budget"), int)
                and not isinstance(project_manifest.get("attempt_budget"), bool)
                and _at_least(artifact.get("attempted"), 1)
                and artifact.get("attempted") <= project_manifest["attempt_budget"]
                    <= generation["maximum_attempts"]
                and project_manifest.get("output_sha256") == artifact.get("sq_config_sha256")
                and project_manifest.get("canonical_evaluation_capital") == 200
                and project_manifest.get("holdout_sealed") is True
                and project_manifest.get("source_role") == "xml_format_scaffold_only",
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "temporal_validation":
        candidate_metrics = artifact.get("candidate_temporal_metrics")
        checks = {
            "OOS_TRADES": _at_least(artifact.get("oos_trades"), temporal["minimum_trades_oos"]),
            "POSITIVE_WINDOWS": _at_least(artifact.get("positive_windows_ratio"), temporal["minimum_positive_windows_ratio"]),
            "OOS_PF": _at_least(artifact.get("oos_profit_factor"), temporal["minimum_oos_profit_factor"]),
            "OOS_DD": _at_most(artifact.get("oos_drawdown_pct"), temporal["maximum_oos_drawdown_pct"]),
            "EXPECTANCY_DECAY": _at_most(artifact.get("train_oos_expectancy_decay_pct"), temporal["maximum_train_oos_expectancy_decay_pct"]),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
        if methodology.get("schema_version", 1) >= 4:
            ids = receipt.get("candidate_ids", [])
            valid = (isinstance(candidate_metrics, dict) and bool(candidate_metrics)
                     and set(candidate_metrics) == set(ids)
                     and all(isinstance(metric, dict) for metric in candidate_metrics.values()))
            valid = valid and all(
                _at_least(metric.get("oos_trades"), 0)
                and _between(metric.get("positive_windows_ratio"), 0, 1)
                and _at_least(metric.get("oos_profit_factor"), 0)
                and _between(metric.get("oos_drawdown_pct"), 0, 100)
                and _number(metric.get("train_oos_expectancy_decay_pct"))
                for metric in candidate_metrics.values())
            checks.update({
                "CANDIDATE_METRICS": valid,
                "OOS_TRADES_RECOMPUTES": valid and artifact.get("oos_trades")
                    == min(metric["oos_trades"] for metric in candidate_metrics.values()),
                "POSITIVE_WINDOWS_RECOMPUTES": valid
                    and artifact.get("positive_windows_ratio") == min(
                        metric["positive_windows_ratio"] for metric in candidate_metrics.values()),
                "OOS_PF_RECOMPUTES": valid and artifact.get("oos_profit_factor")
                    == min(metric["oos_profit_factor"] for metric in candidate_metrics.values()),
                "OOS_DD_RECOMPUTES": valid and artifact.get("oos_drawdown_pct")
                    == max(metric["oos_drawdown_pct"] for metric in candidate_metrics.values()),
                "EXPECTANCY_DECAY_RECOMPUTES": valid
                    and artifact.get("train_oos_expectancy_decay_pct") == max(
                        metric["train_oos_expectancy_decay_pct"]
                        for metric in candidate_metrics.values()),
            })
    elif stage == "robustness":
        candidate_metrics = artifact.get("candidate_robustness_metrics")
        checks = {
            "MC_RUNS": _at_least(artifact.get("monte_carlo_runs"), robust["monte_carlo_runs"]),
            "MC_PROFITABLE": _at_least(artifact.get("profitable_monte_carlo_ratio"), robust["minimum_profitable_monte_carlo_ratio"]),
            "PARAMETER_PERTURBATION": artifact.get("parameter_perturbation_pct") == robust["parameter_perturbation_pct"],
            "COST_STRESS": _at_least(artifact.get("cost_stress_multiplier"), robust["cost_stress_multiplier"]),
            "STRESS_PF": _at_least(artifact.get("stress_profit_factor"), robust["minimum_stress_profit_factor"]),
            "LIQUIDATION": _at_most(artifact.get("liquidation_probability"), robust["maximum_liquidation_probability"]),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
        if methodology.get("schema_version", 1) >= 4:
            ids = receipt.get("candidate_ids", [])
            valid = (isinstance(candidate_metrics, dict) and bool(candidate_metrics)
                     and set(candidate_metrics) == set(ids)
                     and all(isinstance(metric, dict) for metric in candidate_metrics.values()))
            valid = valid and all(
                _at_least(metric.get("monte_carlo_runs"), 0)
                and _between(metric.get("profitable_monte_carlo_ratio"), 0, 1)
                and _at_least(metric.get("stress_profit_factor"), 0)
                and _between(metric.get("liquidation_probability"), 0, 1)
                for metric in candidate_metrics.values())
            checks.update({
                "CANDIDATE_METRICS": valid,
                "MC_RUNS_RECOMPUTES": valid and artifact.get("monte_carlo_runs")
                    == min(metric["monte_carlo_runs"] for metric in candidate_metrics.values()),
                "MC_PROFITABLE_RECOMPUTES": valid
                    and artifact.get("profitable_monte_carlo_ratio") == min(
                        metric["profitable_monte_carlo_ratio"]
                        for metric in candidate_metrics.values()),
                "STRESS_PF_RECOMPUTES": valid and artifact.get("stress_profit_factor")
                    == min(metric["stress_profit_factor"] for metric in candidate_metrics.values()),
                "LIQUIDATION_RECOMPUTES": valid and artifact.get("liquidation_probability")
                    == max(metric["liquidation_probability"] for metric in candidate_metrics.values()),
            })
    elif stage == "small_account_economics":
        capital = artifact.get("capital_usdc")
        leverage = artifact.get("selected_leverage")
        venue_max = artifact.get("venue_max_leverage")
        notional = artifact.get("position_notional_usdc")
        collateral = artifact.get("collateral_usdc")
        stop_distance = artifact.get("stop_distance_pct")
        liquidation_distance = artifact.get("liquidation_distance_pct")
        evaluated = artifact.get("evaluated_leverage_grid")
        leverage_numeric = isinstance(leverage, (int, float)) and not isinstance(leverage, bool)
        venue_numeric = isinstance(venue_max, (int, float)) and not isinstance(venue_max, bool)
        expected_grid = ([value for value in small["leverage_grid"] if value <= venue_max]
                         if venue_numeric else None)
        higher = ([value for value in expected_grid if value > leverage]
                  if expected_grid is not None and leverage in expected_grid else None)
        rejections = artifact.get("higher_leverage_rejection_reasons")
        computed_margin = (collateral / capital * 100
                           if _at_least(collateral, 0) and _at_least(capital, 1) else None)
        computed_risk = (notional * stop_distance / capital
                         if _at_least(notional, 0) and _at_least(stop_distance, 0)
                         and _at_least(capital, 1) else None)
        computed_buffer = (liquidation_distance / stop_distance
                           if _at_least(liquidation_distance, 0)
                           and _at_least(stop_distance, 0.0000001) else None)
        computed_collateral = (notional / leverage
                               if _at_least(notional, 0.0000001)
                               and leverage_numeric and leverage >= 1 else None)
        reported_margin = artifact.get("portfolio_margin_pct")
        reported_reserve = artifact.get("reserve_pct")
        reported_risk = artifact.get("risk_per_trade_pct")
        reported_buffer = artifact.get("stop_to_liquidation_buffer_ratio")
        checks = {
            "CAPITAL": artifact.get("capital_usdc") == small["canonical_capital_usdc"],
            "EXPECTANCY": _at_least(artifact.get("net_expectancy_usdc"), small["minimum_net_expectancy_usdc"]),
            "NET_PF": _at_least(artifact.get("net_profit_factor"), small["minimum_net_profit_factor"]),
            "RISK": _at_most(artifact.get("risk_per_trade_pct"), small["maximum_risk_per_trade_pct"]),
            "MARGIN": _at_most(artifact.get("portfolio_margin_pct"), small["maximum_portfolio_margin_pct"]),
            "RESERVE": _at_least(artifact.get("reserve_pct"), small["minimum_reserve_pct"]),
            "LEVERAGE": leverage in small["leverage_grid"],
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
        if methodology.get("schema_version", 1) >= 4:
            checks.update({
                "SINGLE_CANDIDATE": len(receipt.get("candidate_ids", [])) == 1,
                "VENUE_LEVERAGE": leverage_numeric and venue_numeric and venue_max >= leverage,
                "LEVERAGE_POLICY": artifact.get("leverage_selection_policy")
                    == small["leverage_selection_policy"],
                "LEVERAGE_GRID": expected_grid is not None and evaluated == expected_grid,
                "MAXIMUM_SAFE": higher is not None and isinstance(rejections, dict)
                    and set(rejections) == {str(value) for value in higher}
                    and all(isinstance(reason, str) and bool(reason.strip())
                            for reason in rejections.values()),
                "STOP_REQUIRED": artifact.get("stop_loss_required") is True
                    and small.get("required_stop_loss") is True,
                "NOTIONAL": _at_least(notional, 0.0000001),
                "COLLATERAL_RECOMPUTES": computed_collateral is not None
                    and _at_least(collateral, 0)
                    and abs(collateral - computed_collateral) <= 1e-9,
                "MARGIN_RECOMPUTES": computed_margin is not None
                    and _at_least(reported_margin, 0)
                    and abs(computed_margin - reported_margin) <= 1e-9,
                "RESERVE_RECOMPUTES": computed_margin is not None
                    and _at_least(reported_reserve, 0)
                    and abs((100 - computed_margin) - reported_reserve) <= 1e-9,
                "RISK_RECOMPUTES": computed_risk is not None
                    and _at_least(reported_risk, 0)
                    and abs(computed_risk - reported_risk) <= 1e-9,
                "LIQUIDATION_MODEL": artifact.get("liquidation_model") == "ostium_exact",
                "LIQUIDATION_BUFFER": computed_buffer is not None
                    and _at_least(reported_buffer, 0)
                    and abs(computed_buffer - reported_buffer) <= 1e-9
                    and computed_buffer >= small["minimum_stop_to_liquidation_buffer_ratio"],
            })
    elif stage == "python_translation":
        source_paths = {"candidate": artifact.get("sqx_path")}
        source_hashes = {"candidate": artifact.get("sqx_sha256")}
        ir_paths = {"candidate": artifact.get("canonical_ir_path")}
        ir_hashes = {"candidate": artifact.get("canonical_ir_sha256")}
        checks = {
            "EXACT": artifact.get("translation_exact") is True and receipt.get("translation_exact") is True,
            "SUPPORTED": artifact.get("supported_subset") is True,
            "SQX_HASH": isinstance(artifact.get("sqx_sha256"), str) and len(artifact["sqx_sha256"]) == 64,
            "IR_HASH": isinstance(artifact.get("canonical_ir_sha256"), str) and len(artifact["canonical_ir_sha256"]) == 64,
        }
        if methodology.get("schema_version", 1) >= 4:
            checks.update({
                "SQX_FILE": _verified_files(
                    source_paths, source_hashes, ["candidate"], receipt.get("artifact", "")),
                "IR_FILE": _verified_files(
                    ir_paths, ir_hashes, ["candidate"], receipt.get("artifact", "")),
            })
    elif stage == "parity":
        report = _verified_json(
            artifact.get("parity_report_path"), artifact.get("parity_report_sha256"),
            receipt.get("artifact", ""))
        checks = {
            "PASS": artifact.get("parity_pass") is True and receipt.get("parity_pass") is True,
            "SIGNALS": artifact.get("signal_match_rate") == 1.0,
            "TRADES": artifact.get("trade_match_rate") == 1.0,
            "CANDLE_COVERAGE": _at_least(artifact.get("candle_coverage_pct"), 95.0),
            "PNL_CORRELATION": _at_least(artifact.get("pnl_correlation"), 0.99),
        }
        if methodology.get("schema_version", 1) >= 4:
            ids = receipt.get("candidate_ids", [])
            checks.update({
                "REPORT_FILE": report is not None,
                "REPORT_CONTRACT": report is not None and len(ids) == 1
                    and report.get("schema_version") == 1
                    and report.get("candidate_id") == ids[0]
                    and report.get("signal_match_rate") == artifact.get("signal_match_rate")
                    and report.get("trade_match_rate") == artifact.get("trade_match_rate")
                    and report.get("candle_coverage_pct") == artifact.get("candle_coverage_pct")
                    and report.get("pnl_correlation") == artifact.get("pnl_correlation"),
            })
    elif stage == "paper":
        paper_config = _verified_json(
            artifact.get("paper_config_path"), artifact.get("paper_config_sha256"),
            receipt.get("artifact", ""))
        checks = {
            "MODE": artifact.get("mode") == "paper",
            "PROBE": artifact.get("paper_probe_configured") is True,
            "LIVE_FALSE": artifact.get("live_authorized") is False,
        }
        if methodology.get("schema_version", 1) >= 4:
            ids = receipt.get("candidate_ids", [])
            checks.update({
                "CONFIG_FILE": paper_config is not None,
                "CONFIG_CONTRACT": paper_config is not None and len(ids) == 1
                    and paper_config.get("schema_version") == 1
                    and paper_config.get("candidate_id") == ids[0]
                    and paper_config.get("capital_usdc") == 200
                    and paper_config.get("mode") == "paper"
                    and paper_config.get("live_authorized") is False
                    and paper_config.get("signer_enabled") is False,
            })
    else:
        checks = {"KNOWN_STAGE": False}
    errors.extend(f"{prefix}:{name}" for name, passed in checks.items() if not passed)
    return errors
