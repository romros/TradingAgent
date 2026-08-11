#!/usr/bin/env python3
"""Verify the sealed crypto H4 signal/execution semantics contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("semantics must be a JSON object")
    return value


def verify(path: Path) -> dict[str, Any]:
    path = path.resolve()
    value = _load(path)
    design = Path(str(value.get("experiment_design_path", "")))
    if not design.is_absolute():
        design = (path.parent / design).resolve()
    bars = value.get("bar_contract") or {}
    positions = value.get("position_contract") or {}
    economics = value.get("economics_contract") or {}
    acceptance = value.get("screen_acceptance_contract") or {}
    temporal = value.get("temporal_contract") or {}
    gaps = value.get("data_gap_contract") or {}
    momentum = (value.get("indicator_contract") or {}).get("time_series_momentum") or {}
    sq = value.get("strategyquant_generation_contract") or {}
    money = sq.get("money_management") or {}
    errors = []
    if value.get("schema_version") != 1: errors.append("SCHEMA")
    if value.get("semantics_id") != "crypto-h4-signal-semantics-v4": errors.append("ID")
    if value.get("selected_before_performance") is not True: errors.append("TIMING")
    if not design.is_file() or value.get("experiment_design_sha256") != sha256(design):
        errors.append("EXPERIMENT_DESIGN_BINDING")
    if (bars.get("timeframe"), bars.get("timezone"), bars.get("entry_timing")) != (
            "H4", "UTC", "next_bar_open"):
        errors.append("BAR_TIMING")
    if (positions.get("maximum_concurrent_positions_per_branch") != 1
            or positions.get("same_bar_priority") != ["stop", "time_exit"]
            or positions.get("unfinished_position_at_train_boundary") != "exclude"
            or positions.get("compounding_during_hypothesis_screen") is not False):
        errors.append("POSITION_ORDERING")
    if (economics.get("account_usdc") != 200
            or economics.get("screen_notional_usdc") != 200
            or economics.get("leverage_during_hypothesis_screen") != 1
            or economics.get("positive_funding_credit_as_alpha") is not False):
        errors.append("SMALL_ACCOUNT_ECONOMICS")
    if (acceptance.get("minimum_closed_trades") != 50
            or acceptance.get("minimum_profit_factor_each_cost_scenario") != 1.2
            or acceptance.get("required_local_neighbors_passing_including_central") != 3
            or acceptance.get("accepted_candidates_global_budget") != 60
            or acceptance.get("overlapping_region_policy") !=
            "greedy_ranked_keep_first_and_suppress_any_same_hypothesis_region_sharing_a_member_attempt"
            or acceptance.get("global_budget_application") !=
            "after_region_overlap_suppression"):
        errors.append("ACCEPTANCE")
    neighbor = acceptance.get("neighbor_definition") or {}
    if (neighbor.get("same_directed_hypothesis_required") is not True
            or neighbor.get("nearest_points_considered") != 4
            or neighbor.get("maximum_normalized_distance") != .15
            or neighbor.get("minimum_nearest_points_passing") != 2
            or neighbor.get("tie_break") != "attempt_ascending"):
        errors.append("NEIGHBORHOOD")
    if (temporal.get("screen_visible_period") != "train_only_from_preregistration"
            or temporal.get("validation_accessed") is not False
            or temporal.get("oos_accessed") is not False
            or temporal.get("final_holdout_accessed") is not False):
        errors.append("TEMPORAL_SEAL")
    if (gaps.get("expected_bar_spacing_hours") != 4
            or gaps.get("imputation_allowed") is not False
            or gaps.get("indicator_window_crossing_gap") != "invalid"
            or gaps.get("open_position_crossing_gap") != "exclude_trade"
            or gaps.get("gap_is_not_a_synthetic_exit") is not True):
        errors.append("DATA_GAPS")
    roc_receipt_path = Path(str(momentum.get("sq_source_contract_path", "")))
    if not roc_receipt_path.is_absolute():
        roc_receipt_path = (path.parent / roc_receipt_path).resolve()
    try:
        roc_receipt = _load(roc_receipt_path) if roc_receipt_path.is_file() else {}
    except (OSError, json.JSONDecodeError, ValueError):
        roc_receipt = {}
    roc_sources = roc_receipt.get("installed_sources") or {}
    roc_sources_valid = True
    for key in ("roc", "above", "below"):
        source = roc_sources.get(key) or {}
        source_path = Path(str(source.get("path", "")))
        if not source_path.is_file() or source.get("sha256") != sha256(source_path):
            roc_sources_valid = False
    if (momentum.get("roc_threshold_domain_pct") != "0_to_15_inclusive_step_0.5"
            or roc_receipt.get("decision") != "PASS_SQ_ROC_SOURCE_CONTRACT"
            or not roc_sources_valid
            or (roc_receipt.get("semantics") or {}).get("roc_pct") !=
            "(current_close-close_period_bars_ago)/close_period_bars_ago*100"
            or (roc_receipt.get("semantics") or {}).get("above_comparison") !=
            "strict_greater_than"
            or (roc_receipt.get("semantics") or {}).get("below_comparison") !=
            "strict_less_than"):
        errors.append("SQ_ROC_SEMANTICS")
    if (sq.get("version") != "143.2708"
            or sq.get("search_method") != "genetic_evolution"
            or sq.get("nominal_evaluations") != 10_000
            or sq.get("attempt_stop_guard") != 64
            or sq.get("wall_time_budget_minutes") != 240
            or (sq.get("islands"), sq.get("population_per_island"),
                sq.get("max_generations")) != (4, 100, 25)
            or sq.get("islands") * sq.get("population_per_island") *
            sq.get("max_generations") != sq.get("nominal_evaluations")
            or (sq.get("crossover_probability_pct"),
                sq.get("mutation_probability_pct"),
                sq.get("migration_every_generations"),
                sq.get("migration_rate_pct"),
                sq.get("initial_population_mode")) != (80, 20, 5, 10, 2)
            or sq.get("maximum_rules") != 3
            or sq.get("initial_capital_usdc") != 200
            or sq.get("normalized_notional_usdc") != 200
            or sq.get("discovery_leverage") != 1
            or sq.get("sq_embedded_spread") != 0
            or sq.get("sq_embedded_commission") != 0
            or sq.get("external_ostium_cost_revalidation_required") is not True
            or sq.get("sq_translation_scope") !=
            "proposal_generation_only_until_python_parity"
            or sq.get("maximum_promoted_candidate_per_stable_region") != 1):
        errors.append("STRATEGYQUANT_GENERATION")
    atr_difference_path = Path(str(sq.get("native_atr_difference_contract_path", "")))
    if not atr_difference_path.is_absolute():
        atr_difference_path = (path.parent / atr_difference_path).resolve()
    try:
        atr_difference = _load(atr_difference_path) if atr_difference_path.is_file() else {}
    except (OSError, json.JSONDecodeError, ValueError):
        atr_difference = {}
    atr_source = Path(str((atr_difference.get("installed_atr_source") or {}).get(
        "path", "")))
    if (atr_difference.get("decision") != "BLOCK_NATIVE_SQ_ATR_FULL_PARITY"
            or atr_difference.get("custom_gap_safe_atr_required_for_native_parity")
            is not True or not atr_source.is_file()
            or (atr_difference.get("installed_atr_source") or {}).get("sha256") !=
            sha256(atr_source)):
        errors.append("SQ_NATIVE_ATR_DIFFERENCE")
    money_path = Path(str(money.get("source_contract_path", "")))
    if not money_path.is_absolute():
        money_path = (path.parent / money_path).resolve()
    try:
        money_receipt = _load(money_path) if money_path.is_file() else {}
    except (OSError, json.JSONDecodeError, ValueError):
        money_receipt = {}
    installed_source = Path(str(money_receipt.get("installed_source_path", "")))
    if (money.get("method") != "CryptoSizeByPrice"
            or money.get("use_account_balance") is not False
            or money.get("maximum_size") != 100
            or money.get("decimals_by_market") != {"BTCUSD": 4, "ETHUSD": 3}
            or money.get("fallback_to_size_one_allowed") is not False
            or money_receipt.get("decision") !=
            "PASS_CRYPTO_SIZE_BY_PRICE_SOURCE_CONTRACT"
            or not installed_source.is_file()
            or money_receipt.get("installed_source_sha256") != sha256(installed_source)
            or any((money_receipt.get("alquimia_contract") or {}).get(market, {}).get(
                "fallback_to_one_reachable_on_canonical_history") is not False
                   for market in ("BTCUSD", "ETHUSD"))):
        errors.append("CRYPTO_SIZE_BY_PRICE")
    for key in ("market_data_accessed", "performance_accessed", "research_authorized",
                "sqcli_authorized", "paper_authorized", "live_authorized"):
        if value.get(key) is not False:
            errors.append(f"SEALED_{key.upper()}")
    return {"valid": not errors, "errors": errors, "path": str(path),
            "sha256": sha256(path), "experiment_design_path": str(design),
            "experiment_design_sha256": sha256(design) if design.is_file() else None,
            "contract": value}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantics", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.semantics)
    print(json.dumps({key: result[key] for key in (
        "valid", "errors", "sha256", "experiment_design_sha256")}, indent=2))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
