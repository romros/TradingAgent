#!/usr/bin/env python3
"""Valida el contracte quantitatiu versionat d'Alquimia."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_STAGES_V3 = ["market_preflight", "discovery", "temporal_validation", "robustness", "small_account_economics", "python_translation", "parity", "paper"]
EXPECTED_STAGES_V4 = ["market_preflight", "hypothesis_screen", "sq_generation", "temporal_validation", "robustness", "small_account_economics", "final_holdout_validation", "python_translation", "parity", "paper"]


def validate(config: dict) -> list[str]:
    errors: list[str] = []
    expected = EXPECTED_STAGES_V4 if config.get("schema_version", 1) >= 4 else EXPECTED_STAGES_V3
    if config.get("stages") != expected:
        errors.append("stages: ordre canonic incorrecte")
    split = config.get("temporal_split", {})
    values = [split.get(key) for key in ("train_pct", "validation_pct", "oos_pct", "final_holdout_pct")]
    if any(not isinstance(value, (int, float)) or value <= 0 for value in values):
        errors.append("temporal_split: percentatges positius obligatoris")
    elif sum(values) != 100:
        errors.append("temporal_split: els percentatges han de sumar 100")
    if split.get("embargo_bars", 0) < 1:
        errors.append("temporal_split: embargo_bars ha de ser positiu")
    principles = config.get("principles", {})
    if principles.get("sq_role") != "candidate_generator_only":
        errors.append("principles: SQ nomes pot generar candidats")
    if principles.get("holdout_policy") != "sealed_until_final_gate":
        errors.append("principles: el holdout final ha d'estar segellat")
    generation = (config.get("sq_generation", {}) if config.get("schema_version", 1) >= 4
                  else config.get("discovery", {}))
    if generation.get("robustness_during_generation") is not False:
        errors.append("discovery: robustesa separada de la generacio")
    if config.get("schema_version", 1) >= 4:
        preflight = config.get("market_preflight", {})
        if preflight.get("performance_accessed") is not False:
            errors.append("market_preflight: rendiment ha d'estar segellat")
        if preflight.get("minimum_overall_observation_coverage_ratio", 0) < 0.9:
            errors.append("market_preflight: cobertura global massa feble")
        if preflight.get("minimum_each_period_coverage_ratio", 0) < 0.8:
            errors.append("market_preflight: cobertura per periode massa feble")
        screen = config.get("hypothesis_screen", {})
        if screen.get("future_periods_accessed") is not False:
            errors.append("hypothesis_screen: futurs han d'estar segellats")
        attempts = screen.get("maximum_attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= 5_000:
            errors.append("hypothesis_screen: pressupost d'intents invalid")
        if screen.get("minimum_trades_train", 0) < 50:
            errors.append("hypothesis_screen: mostra train massa petita")
        if screen.get("minimum_profit_factor_train", 0) < 1.2:
            errors.append("hypothesis_screen: PF train massa feble")
        if screen.get("minimum_stable_neighbors", 0) < 2:
            errors.append("hypothesis_screen: regio estable obligatoria")
        if set(screen.get("cost_scenarios_required", [])) != {"base", "conservative", "stress"}:
            errors.append("hypothesis_screen: escenaris de costos incomplets")
        sq_attempts = generation.get("maximum_attempts")
        if (not isinstance(sq_attempts, int) or isinstance(sq_attempts, bool)
                or not 1 <= sq_attempts <= 10_000):
            errors.append("sq_generation: pressupost d'intents invalid")
        max_rules = generation.get("max_rules")
        if (not isinstance(max_rules, int) or isinstance(max_rules, bool)
                or not 1 <= max_rules <= 3):
            errors.append("sq_generation: massa regles")
        if generation.get("selection_policy") != "all_supported_translatable_unique_candidates":
            errors.append("sq_generation: s'han de conservar tots els candidats traduibles")
        if generation.get("search_method") != "genetic_evolution":
            errors.append("sq_generation: cerca genetica obligatoria")
        temporal = config.get("temporal_validation", {})
        if temporal.get("selection_metric") != "pareto_net_expectancy_drawdown_window_stability":
            errors.append("temporal_validation: seleccio Pareto obligatoria")
        if temporal.get("minimum_trades_oos", 0) < 30:
            errors.append("temporal_validation: mostra OOS massa petita")
        if temporal.get("minimum_positive_windows_ratio", 0) < .6:
            errors.append("temporal_validation: finestres positives insuficients")
        if temporal.get("minimum_oos_profit_factor", 0) < 1.15:
            errors.append("temporal_validation: PF OOS massa feble")
        if temporal.get("maximum_oos_drawdown_pct", 100) > 20:
            errors.append("temporal_validation: drawdown OOS massa alt")
        robust = config.get("robustness", {})
        if robust.get("monte_carlo_runs", 0) < 1_000:
            errors.append("robustness: Monte Carlo insuficient")
        if robust.get("minimum_profitable_monte_carlo_ratio", 0) < .7:
            errors.append("robustness: probabilitat rendible massa baixa")
        if robust.get("parameter_perturbation_pct") != 10:
            errors.append("robustness: pertorbacio parametrica ha de ser 10%")
        if robust.get("minimum_parameter_variants", 0) < 4:
            errors.append("robustness: massa pocs veins parametritzats")
        if robust.get("minimum_profitable_parameter_variants_ratio", 0) < .75:
            errors.append("robustness: regio parametrica massa inestable")
        if robust.get("cost_stress_multiplier", 0) < 2:
            errors.append("robustness: estres de costos massa feble")
        if robust.get("maximum_liquidation_probability", 1) > .001:
            errors.append("robustness: probabilitat de liquidacio massa alta")
        parity = config.get("parity", {})
        if parity.get("minimum_matched_signals", 0) < 30:
            errors.append("parity: mostra de senyals massa petita")
        if parity.get("minimum_matched_trades", 0) < 30:
            errors.append("parity: mostra de trades massa petita")
        if parity.get("minimum_signal_match_rate", 0) < 1:
            errors.append("parity: senyals no exigeixen coincidencia exacta")
        if parity.get("minimum_trade_match_rate", 0) < 1:
            errors.append("parity: trades no exigeixen coincidencia exacta")
        if parity.get("minimum_candle_coverage_pct", 0) < 95:
            errors.append("parity: cobertura de candles massa baixa")
        if parity.get("minimum_pnl_correlation", 0) < .99:
            errors.append("parity: correlacio PnL massa baixa")
        if parity.get("maximum_pnl_mean_absolute_error_usdc", 1) > .005:
            errors.append("parity: error mitja de PnL massa alt")
        if parity.get("maximum_pnl_absolute_error_usdc", 1) > .01:
            errors.append("parity: error maxim de PnL massa alt")
        holdout = config.get("final_holdout_validation", {})
        if holdout.get("minimum_trades", 0) < 20:
            errors.append("final_holdout: mostra massa petita")
        if holdout.get("minimum_profit_factor", 0) < 1.1:
            errors.append("final_holdout: PF massa feble")
        if holdout.get("maximum_drawdown_pct", 100) > 20:
            errors.append("final_holdout: drawdown massa alt")
        if holdout.get("minimum_net_expectancy_usdc", 0) < .1:
            errors.append("final_holdout: expectativa neta massa baixa")
        if set(holdout.get("cost_scenarios_required", [])) != {
                "base", "conservative", "stress"}:
            errors.append("final_holdout: costos incomplets")
        if holdout.get("maximum_evaluations") != 1:
            errors.append("final_holdout: nomes es permet una avaluacio")
    small = config.get("small_account", {})
    if small.get("canonical_capital_usdc") != config.get("capital_usdc"):
        errors.append("small_account: capital canonic inconsistent")
    grid = small.get("leverage_grid", [])
    if not grid or grid != sorted(set(grid)) or min(grid) < 1:
        errors.append("small_account: leverage_grid invalid")
    if config.get("schema_version", 1) >= 4:
        if small.get("maximum_risk_per_trade_pct", 100) > 1.5:
            errors.append("small_account: risc per trade massa alt")
        if small.get("maximum_portfolio_margin_pct", 100) > 35:
            errors.append("small_account: marge de cartera massa alt")
        if small.get("minimum_reserve_pct", 0) < 40:
            errors.append("small_account: reserva insuficient")
        if small.get("minimum_net_expectancy_usdc", 0) < .1:
            errors.append("small_account: expectativa neta massa baixa")
        if small.get("minimum_net_profit_factor", 0) < 1.1:
            errors.append("small_account: PF net massa feble")
        if small.get("minimum_trades", 0) < 30:
            errors.append("small_account: mostra de trades massa petita")
        if set(small.get("cost_scenarios_required", [])) != {
                "base", "conservative", "stress"}:
            errors.append("small_account: costos incomplets")
        if small.get("maximum_single_trade_loss_pct", 100) > 3:
            errors.append("small_account: perdua maxima per trade massa alta")
        if small.get("candidate_selection_policy") != (
                "max_worst_cost_expectancy_then_profit_factor_then_candidate_id"):
            errors.append("small_account: seleccio de candidat no determinista")
        if small.get("leverage_selection_policy") != "maximum_safe_in_grid_up_to_venue_limit":
            errors.append("small_account: politica de leverage maxim segur obligatoria")
        if small.get("required_stop_loss") is not True:
            errors.append("small_account: stop obligatori")
        if small.get("minimum_stop_to_liquidation_buffer_ratio", 0) < 1.5:
            errors.append("small_account: buffer de liquidacio insuficient")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate(config)
    print(json.dumps({"valid": not errors, "methodology_id": config.get("methodology_id"), "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
