#!/usr/bin/env python3
"""Strict, deterministic contracts for Alquimia v3 stage evidence artifacts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from lab.sq_bridge.sq_project_contract import verify_genetic_project
from lab.sq_bridge.sqcli_transport import parse_project_final_log
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir
from lab.sq_bridge.parity_artifact_v4 import compare_traces
from lab.sq_bridge.final_holdout_artifact_v4 import evaluate_trace as evaluate_holdout_trace
from lab.sq_bridge.paper_package_artifact_v4 import verify_package
from lab.sq_bridge.temporal_validation_artifact_v4 import (
    evaluate_trace as evaluate_temporal_trace,
    pareto as temporal_pareto,
)
from lab.sq_bridge.robustness_artifact_v4 import evaluate_trace as evaluate_robustness_trace
from lab.sq_bridge.small_account_artifact_v4 import evaluate_trace as evaluate_small_trace
from lab.sq_bridge.hypothesis_screen_artifact_v4 import (
    evaluate_trace as evaluate_screen_trace,
    verify_source_trade_replay,
)
from lab.sq_bridge.us500_d1_market_preflight_v4 import compose as compose_us500_preflight
from lab.sq_bridge.eurusd_d1_market_preflight_v4 import compose as compose_eurusd_preflight
from lab.sq_bridge.temporal_split_contract_v4 import digest as temporal_digest, sq_periods


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


def _verified_sq_project(path_value: Any, digest: Any, artifact_path: str,
                         manifest: dict | None, reported_shape: Any) -> bool:
    if (manifest is None or not isinstance(path_value, str) or not path_value
            or not isinstance(digest, str)):
        return False
    path = Path(path_value)
    path = path if path.is_absolute() else Path(artifact_path).resolve().parent / path
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        return False
    try:
        return verify_genetic_project(path, manifest) == reported_shape
    except (OSError, TypeError, ValueError):
        return False


def _verified_sq_final_log(watchdog: dict | None, artifact_path: str) -> bool:
    if watchdog is None or watchdog.get("attempt_counter_source") != "sq_project_final_log":
        return False
    value, digest = watchdog.get("sq_final_log_path"), watchdog.get(
        "sq_final_log_sha256")
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        return False
    path = Path(value)
    path = path if path.is_absolute() else Path(artifact_path).resolve().parent / path
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        return False
    try:
        stats = parse_project_final_log(path.read_text())
    except (OSError, RuntimeError):
        return False
    return (stats.get("generated") == watchdog.get("generated")
            and stats.get("accepted") == watchdog.get("in_databank")
            and stats.get("rejected") == watchdog.get("rejected"))


def _verified_temporal_sources(artifact: dict, reported: Any,
                               artifact_path: str, gate: dict) -> bool:
    paths, hashes = artifact.get("temporal_trace_paths"), artifact.get(
        "temporal_trace_sha256")
    if not isinstance(reported, dict) or not _verified_files(
            paths, hashes, sorted(reported), artifact_path):
        return False
    cost_model = _verified_json(
        artifact.get("cost_model_path"), artifact.get("cost_model_sha256"),
        artifact_path)
    if cost_model is None:
        return False
    base = Path(artifact_path).resolve().parent
    recomputed = {}
    try:
        for candidate_id, value in paths.items():
            path = Path(value)
            path = path if path.is_absolute() else base / path
            trace = json.loads(path.read_text())
            if trace.get("source") != "strategyquant_orders_export":
                return False
            metrics = evaluate_temporal_trace(
                trace, gate, cost_model,
                artifact.get("cost_model_sha256"))
            if metrics.pop("candidate_id") != candidate_id:
                return False
            recomputed[candidate_id] = metrics
    except (OSError, TypeError, ValueError):
        return False
    return recomputed == reported


def _verified_robustness_sources(artifact: dict, reported: Any,
                                 artifact_path: str, gate: dict) -> bool:
    paths, hashes = artifact.get("robustness_trace_paths"), artifact.get(
        "robustness_trace_sha256")
    if not isinstance(reported, dict) or not _verified_files(
            paths, hashes, sorted(reported), artifact_path):
        return False
    cost_model = _verified_json(
        artifact.get("cost_model_path"), artifact.get("cost_model_sha256"),
        artifact_path)
    if cost_model is None:
        return False
    base = Path(artifact_path).resolve().parent
    recomputed = {}
    try:
        for candidate_id, value in paths.items():
            path = Path(value)
            path = path if path.is_absolute() else base / path
            trace = json.loads(path.read_text())
            if trace.get("candidate_id") != candidate_id:
                return False
            recomputed[candidate_id] = evaluate_robustness_trace(
                trace, gate, cost_model, artifact.get("cost_model_sha256"))
    except (OSError, KeyError, TypeError, ValueError):
        return False
    return recomputed == reported


def _verified_small_account_sources(artifact: dict, reported: Any,
                                    artifact_path: str, gate: dict,
                                    campaign_id: str) -> bool:
    robust = _verified_json(
        artifact.get("robustness_artifact_path"),
        artifact.get("robustness_artifact_sha256"), artifact_path)
    if (robust is None or robust.get("stage") != "robustness"
            or robust.get("decision") != "PASS"
            or robust.get("campaign_id") != campaign_id):
        return False
    cost_model = _verified_json(
        artifact.get("cost_model_path"), artifact.get("cost_model_sha256"),
        artifact_path)
    if (cost_model is None or cost_model.get("decision") != "PASS_COSTS_FROZEN"
            or cost_model.get("costs_frozen") is not True):
        return False
    cost_hash = artifact.get("cost_model_sha256")
    robust_metrics = robust.get("candidate_robustness_metrics")
    paths, hashes = artifact.get("small_account_trace_paths"), artifact.get(
        "small_account_trace_sha256")
    if (not isinstance(reported, dict) or not isinstance(robust_metrics, dict)
            or set(reported) != set(robust_metrics)
            or not _verified_files(paths, hashes, sorted(reported), artifact_path)):
        return False
    base = Path(artifact_path).resolve().parent
    recomputed = {}
    try:
        for candidate_id, value in paths.items():
            path = Path(value)
            path = path if path.is_absolute() else base / path
            trace = json.loads(path.read_text())
            if trace.get("candidate_id") != candidate_id:
                return False
            recomputed[candidate_id] = evaluate_small_trace(
                trace, gate, robust_metrics[candidate_id], cost_model, cost_hash)
    except (OSError, KeyError, TypeError, ValueError):
        return False
    return recomputed == reported


def _verified_hypothesis_screen_source(artifact: dict, artifact_path: str,
                                       gate: dict) -> bool:
    trace = _verified_json(
        artifact.get("hypothesis_screen_trace_path"),
        artifact.get("hypothesis_screen_trace_sha256"), artifact_path)
    if trace is None:
        return False
    cost_model = _verified_json(
        artifact.get("cost_model_path"), artifact.get("cost_model_sha256"),
        artifact_path)
    if cost_model is None:
        return False
    try:
        result = evaluate_screen_trace(
            trace, gate, cost_model, artifact.get("cost_model_sha256"))
    except (KeyError, TypeError, ValueError):
        return False
    selected = result["selected_hypothesis_ids"]
    evaluated = result["evaluated_hypothesis_metrics"]
    selected_metrics = {key: {
        "train_trades": evaluated[key]["train_trades"],
        "profit_factor_by_cost": evaluated[key]["profit_factor_by_cost"],
        "stable_neighbor_count": evaluated[key]["stable_neighbor_count"],
    } for key in selected}
    return (artifact.get("producer_id") == trace.get("producer_id")
            and artifact.get("source_trade_replay_verified") is True
            and verify_source_trade_replay(trace)
            and artifact.get("attempted") == result["attempted"]
            and artifact.get("evaluated_hypothesis_metrics") == evaluated
            and artifact.get("selected_hypothesis_ids") == selected
            and artifact.get("selected_hypothesis_metrics") == selected_metrics
            and artifact.get("screen_notional_usdc") == result["screen_notional_usdc"]
            and artifact.get("cost_notional_bucket_usdc")
                == result["cost_notional_bucket_usdc"]
            and artifact.get("cost_roundtrip_bps_by_scenario")
                == result["cost_roundtrip_bps_by_scenario"]
            and artifact.get("cost_variable_roundtrip_bps_by_scenario")
                == result["cost_variable_roundtrip_bps_by_scenario"]
            and artifact.get("cost_fixed_usdc_by_scenario")
                == result["cost_fixed_usdc_by_scenario"])


def _verified_market_preflight_source(artifact: dict, artifact_path: str) -> bool:
    value, digest = artifact.get("campaign_config_path"), artifact.get(
        "campaign_config_sha256")
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        return False
    path = Path(value)
    path = path if path.is_absolute() else Path(artifact_path).resolve().parent / path
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
        config = json.loads(path.read_text())
        composers = {"us500_d1_v4": compose_us500_preflight,
                     "eurusd_d1_v4": compose_eurusd_preflight}
        composer = composers.get(config.get("preflight_composer", "us500_d1_v4"))
        return composer is not None and composer(path) == artifact
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _verified_sqx_contracts(paths: Any, expected_ids: list[str], artifact_path: str,
                            reported_rules: Any, reported_counts: Any,
                            max_rules: int) -> bool:
    if (not isinstance(paths, dict) or set(paths) != set(expected_ids)
            or not isinstance(reported_rules, dict) or set(reported_rules) != set(expected_ids)
            or not isinstance(reported_counts, dict) or set(reported_counts) != set(expected_ids)):
        return False
    base = Path(artifact_path).resolve().parent
    for candidate_id in expected_ids:
        if not isinstance(paths[candidate_id], str) or not paths[candidate_id]:
            return False
        path = Path(paths[candidate_id])
        path = path if path.is_absolute() else base / path
        try:
            contract = extract_sqx(path)
            executable_ir = canonical_ir(contract)
            validate_executable_ir(executable_ir)
        except Exception:  # fitxer SQX no fiable: qualsevol error de parseig falla tancat
            return False
        condition_count = contract.get("maximum_entry_conditions")
        if (contract.get("strategy_name") != candidate_id
                or contract.get("translation_status") != "SUPPORTED_SUBSET"
                or not isinstance(condition_count, int) or isinstance(condition_count, bool)
                or condition_count != reported_rules[candidate_id]
                or contract.get("entry_condition_counts") != reported_counts[candidate_id]
                or not 1 <= condition_count <= max_rules):
            return False
    return True


def _verified_sq_prerequisite_chain(artifact: dict, manifest: dict,
                                    artifact_path: str, campaign_id: str) -> bool:
    value, digest = artifact.get("prerequisite_evidence_chain_path"), artifact.get(
        "prerequisite_evidence_chain_sha256")
    if not isinstance(value, str) or not isinstance(digest, str):
        return False
    path = Path(value)
    path = path if path.is_absolute() else Path(artifact_path).resolve().parent / path
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
        chain = json.loads(path.read_text())
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    receipts = chain.get("receipts")
    manifest_path = Path(str(manifest.get("evidence_chain_path", "")))
    try:
        same_path = manifest_path.resolve() == path.resolve()
    except OSError:
        same_path = False
    temporal_valid = True
    profiles = {
        "d1_breakout": "eurusd_d1_breakout_v4",
        "d1_momentum": "eurusd_d1_momentum_v4",
        "d1_shock_reversion": "eurusd_d1_shock_reversion_v4",
    }
    source_id = manifest.get("source_hypothesis_id")
    if manifest.get("market") == "EURUSD" and source_id in profiles:
        try:
            contract_path = Path(manifest["temporal_split_contract_path"])
            contract = json.loads(contract_path.read_text())
            screen_path = Path(receipts[1]["artifact"])
            screen = json.loads(screen_path.read_text())
            trace_path = Path(screen["hypothesis_screen_trace_path"])
            trace_path = (trace_path if trace_path.is_absolute()
                          else screen_path.resolve().parent / trace_path)
            trace = json.loads(trace_path.read_text())
            temporal_valid = (
                manifest.get("search_profile") == profiles[source_id]
                and manifest.get("temporal_split_contract_sha256")
                    == temporal_digest(contract)
                and manifest.get("temporal_source_sha256") == contract.get("source_sha256")
                and manifest.get("periods") == sq_periods(contract)
                and screen.get("hypothesis_screen_trace_sha256")
                    == hashlib.sha256(trace_path.read_bytes()).hexdigest()
                and trace.get("temporal_contract_sha256") == temporal_digest(contract))
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            temporal_valid = False
    return (temporal_valid
        and same_path and manifest.get("evidence_chain_sha256") == digest
        and chain.get("campaign_id") == campaign_id
        and manifest.get("campaign_id") == campaign_id
        and chain.get("hypothesis_id") == manifest.get("source_hypothesis_id")
        and artifact.get("source_hypothesis_ids") == [chain.get("hypothesis_id")]
        and isinstance(receipts, list) and len(receipts) == 2
        and [row.get("stage") for row in receipts]
            == ["market_preflight", "hypothesis_screen"]
        and all(row.get("decision") == "PASS" for row in receipts)
        and manifest.get("market_preflight_receipt_sha256")
            == receipts[0].get("receipt_sha256")
        and manifest.get("hypothesis_screen_receipt_sha256")
            == receipts[1].get("receipt_sha256"))


def _verified_databank(path_value: Any, expected_count: Any, expected_digest: Any,
                       artifact_path: str) -> tuple[bool, list[dict]]:
    if (not isinstance(path_value, str) or not path_value
            or not isinstance(expected_count, int) or isinstance(expected_count, bool)
            or not isinstance(expected_digest, str)):
        return False, []
    root = Path(path_value)
    root = root if root.is_absolute() else Path(artifact_path).resolve().parent / root
    if not root.is_dir():
        return False, []
    rows = []
    try:
        for path in sorted(root.rglob("*.sqx")):
            rows.append({"path": path.relative_to(root).as_posix(),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    except OSError:
        return False, []
    digest = hashlib.sha256("".join(
        f"{row['path']}:{row['sha256']}\n" for row in rows).encode()).hexdigest()
    return len(rows) == expected_count and digest == expected_digest, rows


def _verified_parity_sources(report: dict | None, report_path_value: Any,
                             artifact_path: str, gate: dict) -> bool:
    if report is None or report.get("schema_version") != 2:
        return False
    report_path = Path(report_path_value)
    report_path = (report_path if report_path.is_absolute()
                   else Path(artifact_path).resolve().parent / report_path)
    traces = []

    def source_lineage(trace: dict, trace_path: Path, source: str) -> bool:
        required = ({"orders": "orders_sha256", "signals": "signals_sha256",
                     "market_data": "market_data_sha256"}
                    if source == "sq" else
                    {"canonical_ir": "canonical_ir_sha256",
                     "market_data": "market_data_sha256"})
        for prefix, digest_key in required.items():
            value, expected = trace.get(f"{prefix}_path"), trace.get(digest_key)
            if not isinstance(value, str) or not value or not isinstance(expected, str):
                return False
            source_path = Path(value)
            source_path = (source_path if source_path.is_absolute()
                           else trace_path.resolve().parent / source_path)
            try:
                if hashlib.sha256(source_path.read_bytes()).hexdigest() != expected:
                    return False
            except OSError:
                return False
        if source == "sq":
            return (trace.get("pnl_semantics")
                    == "recomputed_from_prices_at_fixed_notional_before_costs"
                    and isinstance(trace.get("source_timezone"), str)
                    and bool(trace["source_timezone"]))
        return True
    for source in ("sq", "python"):
        value, digest = report.get(f"{source}_trace_path"), report.get(f"{source}_trace_sha256")
        if not isinstance(value, str) or not value or not isinstance(digest, str):
            return False
        path = Path(value)
        path = path if path.is_absolute() else report_path.resolve().parent / path
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
            trace = json.loads(path.read_text())
        except (OSError, ValueError):
            return False
        if not source_lineage(trace, path, source):
            return False
        traces.append(trace)
    try:
        metrics = compare_traces(traces[0], traces[1])
    except (TypeError, ValueError):
        return False
    metric_keys = {
        "candidate_id", "sq_candle_count", "python_candle_count", "common_candle_count",
        "candle_coverage_pct", "sq_signal_count", "python_signal_count",
        "matched_signal_count", "signal_match_rate", "sq_trade_count",
        "python_trade_count", "matched_trade_count", "trade_match_rate", "pnl_correlation",
        "pnl_mean_absolute_error_usdc", "pnl_max_absolute_error_usdc",
    }
    if any(report.get(key) != metrics[key] for key in metric_keys):
        return False
    expected_pass = (
        metrics["matched_signal_count"] >= gate["minimum_matched_signals"]
        and metrics["matched_trade_count"] >= gate["minimum_matched_trades"]
        and metrics["signal_match_rate"] >= gate["minimum_signal_match_rate"]
        and metrics["trade_match_rate"] >= gate["minimum_trade_match_rate"]
        and metrics["candle_coverage_pct"] >= gate["minimum_candle_coverage_pct"]
        and metrics["pnl_correlation"] >= gate["minimum_pnl_correlation"]
        and metrics["pnl_mean_absolute_error_usdc"]
            <= gate["maximum_pnl_mean_absolute_error_usdc"]
        and metrics["pnl_max_absolute_error_usdc"]
            <= gate["maximum_pnl_absolute_error_usdc"])
    return report.get("parity_pass") is expected_pass


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
                "SOURCE_CONTRACT": _verified_market_preflight_source(
                    artifact, receipt.get("artifact", ""))
                    if provenance != "synthetic_control" else True,
            })
    elif stage == "discovery":
        checks = {
            "SQ_SOURCE": artifact.get("generator") == "StrategyQuant",
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "SELECTED": _ids(artifact.get("selected_candidate_ids")) == receipt.get("candidate_ids", []),
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
        }
    elif stage == "hypothesis_screen":
        screen = {**methodology["hypothesis_screen"],
                  "temporal_split": methodology["temporal_split"]}
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
        if methodology.get("schema_version", 1) >= 4:
            evaluated_hypotheses = artifact.get("evaluated_hypothesis_metrics")
            checks.update({
                "EVALUATED_HYPOTHESES": isinstance(evaluated_hypotheses, dict)
                    and bool(evaluated_hypotheses)
                    and set(selected_hypotheses or []).issubset(evaluated_hypotheses),
                "TRACE_CONTRACT": _verified_hypothesis_screen_source(
                    artifact, receipt.get("artifact", ""), screen)
                    if provenance != "synthetic_control" else True,
            })
    elif stage == "sq_generation":
        generation = methodology["sq_generation"]
        hashes = artifact.get("candidate_artifact_hashes")
        paths = artifact.get("candidate_artifact_paths")
        rules = artifact.get("rules_per_candidate")
        entry_counts = artifact.get("entry_condition_counts_per_candidate")
        candidate_ids = receipt.get("candidate_ids", [])
        negative_generation = (
            receipt.get("decision") == "REJECT" and candidate_ids == []
            and artifact.get("rejection_reason")
                == "NO_SQ_CANDIDATES_WITHIN_FROZEN_BUDGET")
        project_manifest = _verified_json(
            artifact.get("sq_project_manifest_path"),
            artifact.get("sq_project_manifest_sha256"), receipt.get("artifact", ""))
        watchdog_status = _verified_json(
            artifact.get("sq_watchdog_status_path"),
            artifact.get("sq_watchdog_status_sha256"), receipt.get("artifact", ""))
        supervised_run = _verified_json(
            artifact.get("sq_supervised_run_receipt_path"),
            artifact.get("sq_supervised_run_receipt_sha256"), receipt.get("artifact", ""))
        databank_valid, databank_rows = _verified_databank(
            artifact.get("databank_path"), artifact.get("databank_candidate_count"),
            artifact.get("databank_inventory_sha256"), receipt.get("artifact", ""))
        watchdog_rows = ([{"path": row.get("path"), "sha256": row.get("sha256")}
                          for row in watchdog_status.get("artifacts", [])]
                         if watchdog_status is not None
                         and isinstance(watchdog_status.get("artifacts"), list) else None)
        checks = {
            "SQ_SOURCE": artifact.get("generator") == "StrategyQuant",
            "SEARCH_METHOD": artifact.get("search_method") == generation["search_method"],
            "SELECTION_POLICY": artifact.get("selection_policy")
                == generation["selection_policy"],
            "ATTEMPTED": _at_least(artifact.get("attempted"), 1),
            "ATTEMPT_LIMIT": _at_most(
                artifact.get("attempted"), generation["maximum_attempts"]),
            "SELECTED": _ids(artifact.get("selected_candidate_ids")) == receipt.get("candidate_ids", []),
            "SOURCE_HYPOTHESES": bool(_ids(artifact.get("source_hypothesis_ids"))),
            "ARTIFACT_HASHES": isinstance(hashes, dict)
                               and (bool(hashes) or negative_generation)
                               and set(hashes) == set(candidate_ids)
                               and all(isinstance(value, str) and len(value) == 64
                                       for value in hashes.values()),
            "ARTIFACT_FILES": _verified_files(
                paths, hashes, candidate_ids, receipt.get("artifact", "")),
            "RULE_COUNTS": isinstance(rules, dict)
                and (bool(rules) or negative_generation)
                and set(rules) == set(receipt.get("candidate_ids", []))
                and all(isinstance(value, int) and not isinstance(value, bool)
                        and 1 <= value <= generation["max_rules"] for value in rules.values()),
            "DATABANK_FROZEN": artifact.get("databank_frozen") is True,
            "FUTURES_SEALED": artifact.get("future_periods_accessed") is False,
            "CONFIG_HASH": isinstance(artifact.get("sq_config_sha256"), str)
                           and len(artifact["sq_config_sha256"]) == 64,
            "PROJECT_MANIFEST_FILE": project_manifest is not None,
            "PROJECT_MANIFEST_CONTRACT": project_manifest is not None
                and project_manifest.get("schema_version") == 1
                and project_manifest.get("methodology_id") == methodology["methodology_id"]
                and project_manifest.get("generation_type")
                    == generation["search_method"].replace("_", "-")
                and project_manifest.get("attempt_stop_guard")
                    == generation["attempt_stop_guard"]
                and isinstance(project_manifest.get("attempt_budget"), int)
                and not isinstance(project_manifest.get("attempt_budget"), bool)
                and _at_least(artifact.get("attempted"), 1)
                and artifact.get("attempted") <= project_manifest["attempt_budget"]
                    <= generation["maximum_attempts"]
                and project_manifest.get("output_sha256") == artifact.get("sq_config_sha256")
                and project_manifest.get("canonical_evaluation_capital") == 200
                and project_manifest.get("sq_discovery_spread") == 0
                and project_manifest.get("sq_discovery_commission") == 0
                and project_manifest.get("sq_discovery_slippage") == 0
                and project_manifest.get("venue_cost_application_stage")
                    == "post_sq_frozen_cost_model"
                and project_manifest.get("holdout_sealed") is True
                and project_manifest.get("source_role") == "xml_format_scaffold_only",
            "NO_HOLDOUT": artifact.get("holdout_accessed") is False,
            "NEGATIVE_OUTCOME": bool(candidate_ids) or negative_generation,
        }
        if methodology.get("schema_version", 1) >= 4 and provenance != "synthetic_control":
            checks.update({
                "CONFIG_CONTRACT": _verified_sq_project(
                    artifact.get("sq_config_path"), artifact.get("sq_config_sha256"),
                    receipt.get("artifact", ""), project_manifest,
                    artifact.get("sq_genetic_shape")),
                "PREREQUISITE_CHAIN": project_manifest is not None
                    and _verified_sq_prerequisite_chain(
                        artifact, project_manifest, receipt.get("artifact", ""), campaign_id),
                "DATABANK_INVENTORY": databank_valid,
                "WATCHDOG_FILE": watchdog_status is not None,
                "WATCHDOG_FINAL_LOG": _verified_sq_final_log(
                    watchdog_status, receipt.get("artifact", "")),
                "WATCHDOG_CONTRACT": watchdog_status is not None
                    and project_manifest is not None
                    and watchdog_status.get("project") == project_manifest.get("project_name")
                    and watchdog_status.get("generated") == artifact.get("attempted")
                    and watchdog_status.get("state") == "BUDGET_REACHED"
                    and watchdog_status.get("reason") in {
                        "ATTEMPT_BUDGET", "ACCEPTED_TARGET", "WALL_TIME_BUDGET"}
                    and watchdog_rows == databank_rows,
                "SUPERVISED_RUN": supervised_run is not None
                    and watchdog_status is not None
                    and project_manifest is not None
                    and supervised_run.get("decision") == "PASS_SUPERVISED_SQ_RUN"
                    and supervised_run.get("project_name")
                        == project_manifest.get("project_name")
                    and supervised_run.get("generated") == artifact.get("attempted")
                    and supervised_run.get("accepted")
                        == watchdog_status.get("in_databank")
                    and supervised_run.get("watchdog_status_sha256")
                        == artifact.get("sq_watchdog_status_sha256")
                    and supervised_run.get("project_source_cfx_sha256")
                        == artifact.get("sq_config_sha256")
                    and supervised_run.get("sq_imported_cfx_sha256")
                        == artifact.get("sq_imported_cfx_sha256")
                    and supervised_run.get("project_manifest_sha256")
                        == artifact.get("sq_project_manifest_sha256")
                    and supervised_run.get("exact_final_counters") is True
                    and supervised_run.get("within_hard_attempt_budget") is True,
                "IMPORTED_CONFIG_CONTRACT": _verified_sq_project(
                    artifact.get("sq_imported_cfx_path"),
                    artifact.get("sq_imported_cfx_sha256"),
                    receipt.get("artifact", ""), project_manifest,
                    artifact.get("sq_genetic_shape")),
                "SQX_CONTRACTS": _verified_sqx_contracts(
                paths, candidate_ids, receipt.get("artifact", ""), rules, entry_counts,
                generation["max_rules"]),
                "EXECUTION_NORMALIZED": artifact.get(
                    "trade_execution_normalized_per_candidate")
                    == {candidate_id: True for candidate_id in candidate_ids},
                "STOP_LOSS_REQUIRED": artifact.get(
                    "stop_loss_required_satisfied_per_candidate")
                    == {candidate_id: True for candidate_id in candidate_ids},
            })
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
            evaluated = artifact.get("evaluated_candidate_temporal_metrics")
            valid = (isinstance(candidate_metrics, dict) and bool(candidate_metrics)
                     and set(candidate_metrics) == set(ids)
                     and all(isinstance(metric, dict) for metric in candidate_metrics.values()))
            valid = valid and all(
                _at_least(metric.get("oos_trades"), 0)
                and _between(metric.get("positive_windows_ratio"), 0, 1)
                and _at_least(metric.get("oos_profit_factor"), 0)
                and _between(metric.get("oos_drawdown_pct"), 0, 100)
                and _number(metric.get("train_oos_expectancy_decay_pct"))
                and _number(metric.get("net_expectancy_usdc"))
                for metric in candidate_metrics.values())
            evaluated_valid = (isinstance(evaluated, dict) and bool(evaluated)
                and all(isinstance(metric, dict) for metric in evaluated.values())
                and all(
                    _at_least(metric.get("oos_trades"), 0)
                    and _between(metric.get("positive_windows_ratio"), 0, 1)
                    and _at_least(metric.get("oos_profit_factor"), 0)
                    and _between(metric.get("oos_drawdown_pct"), 0, 100)
                    and _number(metric.get("train_oos_expectancy_decay_pct"))
                    and _number(metric.get("net_expectancy_usdc"))
                    for metric in evaluated.values()))
            passing = ({key: metric for key, metric in evaluated.items()
                        if metric["oos_trades"] >= temporal["minimum_trades_oos"]
                        and metric["positive_windows_ratio"]
                            >= temporal["minimum_positive_windows_ratio"]
                        and metric["oos_profit_factor"] >= temporal["minimum_oos_profit_factor"]
                        and metric["oos_drawdown_pct"] <= temporal["maximum_oos_drawdown_pct"]
                        and metric["train_oos_expectancy_decay_pct"]
                            <= temporal["maximum_train_oos_expectancy_decay_pct"]}
                       if evaluated_valid else {})
            pareto = temporal_pareto(passing) if passing else []
            checks.update({
                "CANDIDATE_METRICS": valid,
                "EVALUATED_METRICS": evaluated_valid,
                "TRACE_CONTRACT": _verified_temporal_sources(
                    artifact, evaluated, receipt.get("artifact", ""), temporal)
                    if provenance != "synthetic_control" else True,
                "SELECTION_METRIC": artifact.get("selection_metric")
                    == temporal["selection_metric"],
                "PARETO_RECOMPUTES": evaluated_valid
                    and artifact.get("pareto_candidate_ids") == pareto
                    and ids == pareto
                    and candidate_metrics == {key: evaluated[key] for key in pareto},
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
            evaluated = artifact.get("evaluated_candidate_robustness_metrics")
            valid = (isinstance(candidate_metrics, dict) and bool(candidate_metrics)
                     and set(candidate_metrics) == set(ids)
                     and all(isinstance(metric, dict) for metric in candidate_metrics.values()))
            valid = valid and all(
                _at_least(metric.get("monte_carlo_runs"), 0)
                and _between(metric.get("profitable_monte_carlo_ratio"), 0, 1)
                and _at_least(metric.get("parameter_variant_count"), 0)
                and _between(metric.get("profitable_parameter_variants_ratio"), 0, 1)
                and _at_least(metric.get("stress_profit_factor"), 0)
                and _between(metric.get("liquidation_probability"), 0, 1)
                and metric.get("tested_leverage") in small["leverage_grid"]
                and _at_least(metric.get("venue_max_leverage"), metric.get("tested_leverage", 0))
                and _at_least(metric.get("liquidation_distance_pct"), 0)
                for metric in candidate_metrics.values())
            evaluated_valid = (isinstance(evaluated, dict) and bool(evaluated)
                and all(isinstance(metric, dict) for metric in evaluated.values())
                and all(
                    _at_least(metric.get("monte_carlo_runs"), 0)
                    and _between(metric.get("profitable_monte_carlo_ratio"), 0, 1)
                    and _at_least(metric.get("parameter_variant_count"), 0)
                    and _between(metric.get("profitable_parameter_variants_ratio"), 0, 1)
                    and _at_least(metric.get("stress_profit_factor"), 0)
                    and _between(metric.get("liquidation_probability"), 0, 1)
                    and metric.get("tested_leverage") in small["leverage_grid"]
                    and _at_least(metric.get("venue_max_leverage"), metric.get("tested_leverage", 0))
                    and _at_least(metric.get("liquidation_distance_pct"), 0)
                    for metric in evaluated.values()))
            selected = (sorted(key for key, metric in evaluated.items()
                if metric["monte_carlo_runs"] >= robust["monte_carlo_runs"]
                and metric["profitable_monte_carlo_ratio"]
                    >= robust["minimum_profitable_monte_carlo_ratio"]
                and metric["parameter_variant_count"] >= robust["minimum_parameter_variants"]
                and metric["profitable_parameter_variants_ratio"]
                    >= robust["minimum_profitable_parameter_variants_ratio"]
                and metric["stress_profit_factor"] >= robust["minimum_stress_profit_factor"]
                and metric["liquidation_probability"]
                    <= robust["maximum_liquidation_probability"])
                if evaluated_valid else [])
            source_gate = {**robust, "allowed_leverage_grid": small["leverage_grid"]}
            checks.update({
                "CANDIDATE_METRICS": valid,
                "EVALUATED_METRICS": evaluated_valid,
                "PARAMETER_VARIANTS": _at_least(
                    artifact.get("minimum_parameter_variant_count"),
                    robust["minimum_parameter_variants"]),
                "PARAMETER_VARIANT_PROFITABLE": _at_least(
                    artifact.get("profitable_parameter_variants_ratio"),
                    robust["minimum_profitable_parameter_variants_ratio"]),
                "SELECTION_RECOMPUTES": evaluated_valid and ids == selected
                    and candidate_metrics == {key: evaluated[key] for key in selected},
                "TRACE_CONTRACT": _verified_robustness_sources(
                    artifact, evaluated, receipt.get("artifact", ""), source_gate)
                    if provenance != "synthetic_control" else True,
                "MC_RUNS_RECOMPUTES": valid and artifact.get("monte_carlo_runs")
                    == min(metric["monte_carlo_runs"] for metric in candidate_metrics.values()),
                "MC_PROFITABLE_RECOMPUTES": valid
                    and artifact.get("profitable_monte_carlo_ratio") == min(
                        metric["profitable_monte_carlo_ratio"]
                        for metric in candidate_metrics.values()),
                "PARAMETER_VARIANT_COUNT_RECOMPUTES": valid
                    and artifact.get("minimum_parameter_variant_count") == min(
                        metric["parameter_variant_count"] for metric in candidate_metrics.values()),
                "PARAMETER_VARIANT_PROFITABLE_RECOMPUTES": valid
                    and artifact.get("profitable_parameter_variants_ratio") == min(
                        metric["profitable_parameter_variants_ratio"]
                        for metric in candidate_metrics.values()),
                "STRESS_PF_RECOMPUTES": valid and artifact.get("stress_profit_factor")
                    == min(metric["stress_profit_factor"] for metric in candidate_metrics.values()),
                "LIQUIDATION_RECOMPUTES": valid and artifact.get("liquidation_probability")
                    == max(metric["liquidation_probability"] for metric in candidate_metrics.values()),
                "TESTED_LEVERAGE_RECOMPUTES": valid
                    and artifact.get("maximum_tested_leverage") == min(
                        metric["tested_leverage"] for metric in candidate_metrics.values()),
            })
    elif stage == "small_account_economics":
        capital = artifact.get("capital_usdc")
        leverage = artifact.get("selected_leverage")
        venue_max = artifact.get("venue_max_leverage")
        notional = artifact.get("position_notional_usdc")
        collateral = artifact.get("collateral_usdc")
        entry_cost_buffer = artifact.get("entry_cost_buffer_usdc")
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
        computed_committed = (collateral + entry_cost_buffer
                              if _at_least(collateral, 0)
                              and _at_least(entry_cost_buffer, 0) else None)
        computed_committed_pct = (computed_committed / capital * 100
                                  if computed_committed is not None
                                  and _at_least(capital, 1) else None)
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
        reported_reserve_usdc = artifact.get("reserve_usdc")
        reported_committed = artifact.get("capital_committed_usdc")
        reported_committed_pct = artifact.get("capital_committed_pct")
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
            candidate_evaluated = artifact.get("evaluated_candidate_small_account_metrics")
            candidate_evaluated_valid = (isinstance(candidate_evaluated, dict)
                and bool(candidate_evaluated)
                and all(isinstance(metric, dict) for metric in candidate_evaluated.values()))
            passing = ({key: metric for key, metric in candidate_evaluated.items()
                if metric.get("selected_leverage") is not None
                and _at_least(metric.get("trades"), small["minimum_trades"])
                and _at_least(metric.get("net_expectancy_usdc"),
                              small["minimum_net_expectancy_usdc"])
                and _at_least(metric.get("net_profit_factor"),
                              small["minimum_net_profit_factor"])
                and _at_most(metric.get("maximum_single_trade_loss_pct"),
                             small["maximum_single_trade_loss_pct"])}
                if candidate_evaluated_valid else {})
            ranked = sorted(passing, key=lambda key: (
                -passing[key]["net_expectancy_usdc"],
                -passing[key]["net_profit_factor"], key))
            selected_id = ranked[0] if ranked else None
            selected_metric = (candidate_evaluated.get(selected_id)
                               if selected_id is not None else None)
            checks.update({
                "SINGLE_CANDIDATE": len(receipt.get("candidate_ids", [])) == 1,
                "CANDIDATE_SELECTION_POLICY": artifact.get("candidate_selection_policy")
                    == small["candidate_selection_policy"],
                "EVALUATED_CANDIDATES": candidate_evaluated_valid,
                "CANDIDATE_SELECTION_RECOMPUTES": selected_id is not None
                    and receipt.get("candidate_ids") == [selected_id],
                "SOURCE_TRACE_CONTRACT": _verified_small_account_sources(
                    artifact, candidate_evaluated, receipt.get("artifact", ""),
                    small, campaign_id)
                    if provenance != "synthetic_control" else True,
                "PERFORMANCE_RECOMPUTES": isinstance(selected_metric, dict)
                    and artifact.get("net_expectancy_usdc")
                        == selected_metric.get("net_expectancy_usdc")
                    and artifact.get("net_profit_factor")
                        == selected_metric.get("net_profit_factor"),
                "SIZING_SOURCE_RECOMPUTES": isinstance(selected_metric, dict)
                    and all(artifact.get(key) == selected_metric.get(key) for key in (
                        "risk_per_trade_pct", "portfolio_margin_pct", "reserve_pct",
                        "selected_leverage", "venue_max_leverage",
                        "evaluated_leverage_grid", "higher_leverage_rejection_reasons",
                        "position_notional_usdc", "collateral_usdc",
                        "entry_cost_buffer_usdc", "capital_committed_usdc",
                        "capital_committed_pct", "reserve_usdc",
                        "stop_distance_pct", "liquidation_distance_pct",
                        "stop_to_liquidation_buffer_ratio")),
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
                    and _at_least(reported_reserve_usdc, 0)
                    and computed_committed is not None
                    and abs((capital - computed_committed) - reported_reserve_usdc) <= 1e-9
                    and abs(((capital - computed_committed) / capital * 100)
                            - reported_reserve) <= 1e-9,
                "COMMITTED_CAPITAL_RECOMPUTES": computed_committed is not None
                    and computed_committed_pct is not None
                    and _at_least(reported_committed, 0)
                    and _at_least(reported_committed_pct, 0)
                    and abs(computed_committed - reported_committed) <= 1e-9
                    and abs(computed_committed_pct - reported_committed_pct) <= 1e-9
                    and computed_committed <= capital,
                "RISK_RECOMPUTES": computed_risk is not None
                    and _at_least(reported_risk, 0)
                    and abs(computed_risk - reported_risk) <= 1e-9,
                "LIQUIDATION_MODEL": artifact.get("liquidation_model")
                    == small.get("liquidation_model")
                    == "ostium_threshold_cost_buffered",
                "LIQUIDATION_BUFFER": computed_buffer is not None
                    and _at_least(reported_buffer, 0)
                    and abs(computed_buffer - reported_buffer) <= 1e-9
                    and computed_buffer >= small["minimum_stop_to_liquidation_buffer_ratio"],
            })
    elif stage == "final_holdout_validation":
        gate = methodology["final_holdout_validation"]
        ids = receipt.get("candidate_ids", [])
        metrics_by_candidate = artifact.get("candidate_holdout_metrics")
        metric = (metrics_by_candidate.get(ids[0])
                  if isinstance(metrics_by_candidate, dict) and len(ids) == 1 else None)
        costs = metric.get("profit_factor_by_cost") if isinstance(metric, dict) else None
        expectancy = (metric.get("net_expectancy_usdc_by_cost")
                      if isinstance(metric, dict) else None)
        required_costs = set(gate["cost_scenarios_required"])
        valid = (isinstance(metrics_by_candidate, dict) and set(metrics_by_candidate) == set(ids)
                 and isinstance(metric, dict)
                 and isinstance(costs, dict) and set(costs) == required_costs
                 and isinstance(expectancy, dict) and set(expectancy) == required_costs
                 and _at_least(metric.get("trades"), 0)
                 and all(_at_least(value, 0) for value in costs.values())
                 and all(_number(value) for value in expectancy.values())
                 and _between(metric.get("drawdown_pct"), 0, 100))
        minimum_pf = min(costs.values()) if valid else None
        minimum_expectancy = min(expectancy.values()) if valid else None
        checks = {
            "SINGLE_FROZEN_CANDIDATE": len(ids) == 1
                and artifact.get("selection_frozen_before_holdout") is True,
            "ONE_EVALUATION": artifact.get("holdout_evaluation_count")
                == gate["maximum_evaluations"],
            "NO_RETUNING": artifact.get("parameters_changed_after_holdout") is False,
            "HOLDOUT_OPENED": artifact.get("holdout_accessed") is True,
            "CANDIDATE_METRICS": valid,
            "TRADES": valid and metric["trades"] >= gate["minimum_trades"],
            "TRADES_RECOMPUTES": valid
                and artifact.get("holdout_trades") == metric["trades"],
            "PROFIT_FACTOR": valid and minimum_pf >= gate["minimum_profit_factor"],
            "PROFIT_FACTOR_RECOMPUTES": valid
                and artifact.get("minimum_holdout_profit_factor") == minimum_pf,
            "DRAWDOWN": valid
                and metric["drawdown_pct"] <= gate["maximum_drawdown_pct"],
            "DRAWDOWN_RECOMPUTES": valid
                and artifact.get("holdout_drawdown_pct") == metric["drawdown_pct"],
            "EXPECTANCY": valid
                and minimum_expectancy >= gate["minimum_net_expectancy_usdc"],
            "EXPECTANCY_RECOMPUTES": valid
                and artifact.get("minimum_holdout_net_expectancy_usdc")
                    == minimum_expectancy,
            "COST_SET": isinstance(artifact.get("applied_cost_scenarios"), list)
                and set(artifact["applied_cost_scenarios"]) == required_costs,
        }
        if methodology.get("schema_version", 1) >= 4 and provenance != "synthetic_control":
            holdout_trace = _verified_json(
                artifact.get("holdout_trace_path"), artifact.get("holdout_trace_sha256"),
                receipt.get("artifact", ""))
            sizing = _verified_json(
                artifact.get("small_account_artifact_path"),
                artifact.get("small_account_artifact_sha256"),
                receipt.get("artifact", ""))
            cost_model = _verified_json(
                artifact.get("cost_model_path"), artifact.get("cost_model_sha256"),
                receipt.get("artifact", ""))
            recomputed = None
            sources_match = (sizing is not None and cost_model is not None
                and sizing.get("stage") == "small_account_economics"
                and sizing.get("decision") == "PASS"
                and sizing.get("campaign_id") == campaign_id
                and sizing.get("candidate_ids") == ids
                and sizing.get("cost_model_sha256") == artifact.get("cost_model_sha256"))
            if holdout_trace is not None and sources_match:
                try:
                    recomputed = evaluate_holdout_trace(
                        holdout_trace, gate["cost_scenarios_required"], cost_model,
                        artifact.get("cost_model_sha256"), sizing,
                        artifact.get("small_account_artifact_sha256"))
                except (TypeError, ValueError):
                    recomputed = None
            checks.update({
                "TRACE_FILE": holdout_trace is not None,
                "FROZEN_SIZING_AND_COSTS": sources_match,
                "TRACE_CONTRACT": recomputed is not None and len(ids) == 1
                    and recomputed.get("candidate_id") == ids[0]
                    and metrics_by_candidate == {ids[0]: recomputed}
                    and artifact.get("holdout_trades") == recomputed["trades"]
                    and artifact.get("minimum_holdout_profit_factor")
                        == min(recomputed["profit_factor_by_cost"].values())
                    and artifact.get("holdout_drawdown_pct") == recomputed["drawdown_pct"]
                    and artifact.get("minimum_holdout_net_expectancy_usdc")
                        == min(recomputed["net_expectancy_usdc_by_cost"].values()),
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
            verified_ir = _verified_json(
                artifact.get("canonical_ir_path"), artifact.get("canonical_ir_sha256"),
                receipt.get("artifact", ""))
            checks.update({
                "EXECUTION_NORMALIZED": artifact.get("trade_execution_normalized") is True,
                "STOP_LOSS_REQUIRED": artifact.get("stop_loss_required_satisfied") is True,
                "SQX_FILE": _verified_files(
                    source_paths, source_hashes, ["candidate"], receipt.get("artifact", "")),
                "IR_FILE": _verified_files(
                    ir_paths, ir_hashes, ["candidate"], receipt.get("artifact", "")),
            })
            if provenance != "synthetic_control":
                exact_ir = False
                try:
                    sqx_value = Path(artifact.get("sqx_path", ""))
                    sqx_value = (sqx_value if sqx_value.is_absolute()
                                 else Path(receipt.get("artifact", "")).resolve().parent / sqx_value)
                    contract = extract_sqx(sqx_value)
                    recomputed_ir = canonical_ir(contract)
                    execution_contract = validate_executable_ir(recomputed_ir)
                    exact_ir = (verified_ir == recomputed_ir
                                and len(receipt.get("candidate_ids", [])) == 1
                                and contract.get("strategy_name") == receipt["candidate_ids"][0]
                                and artifact.get("execution_contract") == execution_contract)
                except Exception:  # frontera de fitxers SQX/JSON no fiables
                    exact_ir = False
                checks["CANONICAL_IR"] = exact_ir
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
                    and report.get("schema_version") in {1, 2}
                    and report.get("candidate_id") == ids[0]
                    and report.get("signal_match_rate") == artifact.get("signal_match_rate")
                    and report.get("trade_match_rate") == artifact.get("trade_match_rate")
                    and report.get("candle_coverage_pct") == artifact.get("candle_coverage_pct")
                    and report.get("pnl_correlation") == artifact.get("pnl_correlation")
                    and report.get("pnl_mean_absolute_error_usdc")
                        == artifact.get("pnl_mean_absolute_error_usdc")
                    and report.get("pnl_max_absolute_error_usdc")
                        == artifact.get("pnl_max_absolute_error_usdc")
                    and (report.get("schema_version") == 1 or (
                        report.get("matched_signal_count") == artifact.get("matched_signal_count")
                        and report.get("matched_trade_count") == artifact.get("matched_trade_count")
                        and report.get("parity_pass") == artifact.get("parity_pass"))),
            })
            if provenance != "synthetic_control":
                checks.update({
                    "SIGNAL_SAMPLE": artifact.get("matched_signal_count", 0)
                        >= methodology["parity"]["minimum_matched_signals"],
                    "TRADE_SAMPLE": artifact.get("matched_trade_count", 0)
                        >= methodology["parity"]["minimum_matched_trades"],
                    "TRACE_CONTRACT": _verified_parity_sources(
                        report, artifact.get("parity_report_path"),
                        receipt.get("artifact", ""), methodology["parity"]),
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
                    and paper_config.get("schema_version") in {1, 2}
                    and paper_config.get("candidate_id") == ids[0]
                    and paper_config.get("capital_usdc") == 200
                    and paper_config.get("mode") == "paper"
                    and paper_config.get("live_authorized") is False
                    and paper_config.get("signer_enabled") is False,
            })
            if provenance != "synthetic_control":
                config_value = Path(artifact.get("paper_config_path", ""))
                config_value = (config_value if config_value.is_absolute()
                                else Path(receipt.get("artifact", "")).resolve().parent
                                / config_value)
                checks["PACKAGE_CONTRACT"] = paper_config is not None and verify_package(
                    paper_config, config_value)
    else:
        checks = {"KNOWN_STAGE": False}
    errors.extend(f"{prefix}:{name}" for name, passed in checks.items() if not passed)
    return errors
