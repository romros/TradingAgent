#!/usr/bin/env python3
"""Construeix robustesa v4 des de simulacions congelades per candidat."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from lab.sq_bridge.small_account_artifact_v4 import (
    cost_buffered_liquidation_distance_pct,
    liquidation_cost_erosion_pct,
    liquidation_distance_pct,
    select_cost_envelope,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _number(value: object, message: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(message)
    return float(value)


def _aggregate_net(row: dict, notional: float, variable_roundtrip_bps: float,
                   fixed_cost_usdc: float,
                   carry: dict, label: str) -> float:
    gross = _number(row.get("gross_pnl_usdc"), f"PnL brut {label} invalid")
    trades = _number(row.get("trade_count"), f"Nombre de trades {label} invalid")
    long_days = _number(row.get("long_holding_days"), f"Dies long {label} invalid")
    short_days = _number(row.get("short_holding_days"), f"Dies short {label} invalid")
    if trades < 0 or not trades.is_integer() or long_days < 0 or short_days < 0:
        raise ValueError(f"Exposicio {label} invalida")
    carry_cost = notional / 100 / 365.25 * (
        _number((carry.get("long") or {}).get("stress_annual_cost_pct"),
                "Carry stress long absent") * long_days
        + _number((carry.get("short") or {}).get("stress_annual_cost_pct"),
                  "Carry stress short absent") * short_days)
    return (gross - trades * (notional * variable_roundtrip_bps / 10_000
                              + fixed_cost_usdc) - carry_cost)


def evaluate_trace(trace: dict, gate: dict, cost_model: dict,
                   expected_cost_hash: str) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "robustness_simulation_trace"):
        raise ValueError("Schema de trace de robustesa invalid")
    candidate_id = trace.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id de robustesa absent")
    if trace.get("capital_usdc") != 200 or trace.get("holdout_accessed") is not False:
        raise ValueError("Robustesa ha d'usar 200 USDC sense obrir holdout")
    leverage = _number(trace.get("tested_leverage"), "Leverage provat invalid")
    if leverage not in gate["allowed_leverage_grid"]:
        raise ValueError("Leverage provat fora de la graella")
    venue_max_leverage = _number(
        trace.get("venue_max_leverage"), "Limit de leverage Ostium invalid")
    if venue_max_leverage < leverage:
        raise ValueError("Leverage provat superior al limit Ostium")
    if trace.get("liquidation_model") != gate.get("liquidation_model"):
        raise ValueError("La liquidacio ha d'usar el llindar Ostium amb buffer de costos")
    nominal_liquidation_distance = liquidation_distance_pct(
        leverage, venue_max_leverage)
    if trace.get("cost_stress_multiplier") != gate["cost_stress_multiplier"]:
        raise ValueError("Multiplicador de costos de robustesa invalid")
    if trace.get("cost_model_sha256") != expected_cost_hash:
        raise ValueError("Hash del model de costos de robustesa no coincideix")
    notional = trace.get("evaluation_notional_usdc")
    if notional != gate["evaluation_notional_usdc"]:
        raise ValueError("Nocional canonic de robustesa invalid")
    cost_bucket, variable_bps, fixed_usdc, carry = select_cost_envelope(
        cost_model, float(notional))
    robust_variable_bps = max(
        variable_bps["stress"],
        gate["cost_stress_multiplier"] * variable_bps["base"])
    robust_fixed_usdc = fixed_usdc["stress"]
    robust_bps = (robust_variable_bps
                  + robust_fixed_usdc / float(notional) * 10_000)

    runs = trace.get("monte_carlo_runs")
    if not isinstance(runs, list) or len(runs) != gate["monte_carlo_runs"]:
        raise ValueError("Nombre de simulacions Monte Carlo invalid")
    run_ids, profitable, liquidated = [], 0, 0
    effective_distances, liquidation_erosions = [], []
    for row in runs:
        if not isinstance(row, dict) or not isinstance(row.get("run_id"), str):
            raise ValueError("Simulacio Monte Carlo invalida")
        run_ids.append(row["run_id"])
        pnl = _aggregate_net(row, notional, robust_variable_bps,
                             robust_fixed_usdc, carry, "Monte Carlo")
        adverse_excursion = _number(
            row.get("maximum_adverse_excursion_pct"), "Excursio adversa Monte Carlo invalida")
        if adverse_excursion < 0:
            raise ValueError("Excursio adversa Monte Carlo negativa")
        mae_side = row.get("maximum_adverse_excursion_side")
        mae_days = _number(row.get("maximum_adverse_excursion_holding_days"),
                           "Durada fins MAE Monte Carlo invalida")
        if mae_side not in {"long", "short"} or mae_days < 0:
            raise ValueError("Costat o durada fins MAE Monte Carlo invalid")
        annual = _number((carry.get(mae_side) or {}).get("stress_annual_cost_pct"),
                         "Carry stress fins MAE absent")
        erosion = liquidation_cost_erosion_pct(robust_bps, annual, mae_days)
        effective_distance = cost_buffered_liquidation_distance_pct(
            leverage, venue_max_leverage, robust_bps, annual, mae_days)
        liquidation_erosions.append(erosion)
        effective_distances.append(effective_distance)
        profitable += pnl > 0
        liquidated += adverse_excursion >= effective_distance
    if run_ids != sorted(set(run_ids)):
        raise ValueError("run_id Monte Carlo ha de ser unic i ordenat")

    variants = trace.get("parameter_variants")
    if not isinstance(variants, list) or len(variants) < gate["minimum_parameter_variants"]:
        raise ValueError("Variants parametriques insuficients")
    variant_ids, profitable_variants = [], 0
    for row in variants:
        if not isinstance(row, dict) or not isinstance(row.get("variant_id"), str):
            raise ValueError("Variant parametrica invalida")
        variant_ids.append(row["variant_id"])
        perturbation = _number(row.get("perturbation_pct"), "Pertorbacio invalida")
        if abs(perturbation) != gate["parameter_perturbation_pct"]:
            raise ValueError("La variant no aplica la pertorbacio preregistrada")
        profitable_variants += _aggregate_net(
            row, notional, robust_variable_bps, robust_fixed_usdc,
            carry, "de variant") > 0
    if variant_ids != sorted(set(variant_ids)):
        raise ValueError("variant_id ha de ser unic i ordenat")

    stress = trace.get("stress_trades")
    if not isinstance(stress, list) or len(stress) < 30:
        raise ValueError("Mostra de trades amb costos estressats insuficient")
    stress_pnl = []
    for row in stress:
        if not isinstance(row, dict):
            raise ValueError("Trade estressat invalid")
        gross = _number(row.get("gross_return_pct"), "Retorn brut estressat invalid")
        days = _number(row.get("holding_days"), "Durada estressada invalida")
        side = row.get("side")
        if days < 0 or side not in {"long", "short"}:
            raise ValueError("Costat o durada estressada invalida")
        annual = _number((carry.get(side) or {}).get("stress_annual_cost_pct"),
                         "Carry stress absent")
        net_pct = gross - robust_bps / 100 - annual * days / 365.25
        stress_pnl.append(notional * net_pct / 100)
    wins = sum(value for value in stress_pnl if value > 0)
    losses = -sum(value for value in stress_pnl if value < 0)
    if losses <= 0:
        raise ValueError("Profit factor estressat no estimable")
    return {
        "monte_carlo_runs": len(runs),
        "profitable_monte_carlo_ratio": profitable / len(runs),
        "parameter_variant_count": len(variants),
        "profitable_parameter_variants_ratio": profitable_variants / len(variants),
        "stress_profit_factor": wins / losses,
        "liquidation_probability": liquidated / len(runs),
        "tested_leverage": leverage,
        "venue_max_leverage": venue_max_leverage,
        "liquidation_model": "ostium_threshold_cost_buffered",
        "nominal_liquidation_distance_pct": nominal_liquidation_distance,
        "minimum_cost_buffered_liquidation_distance_pct": min(effective_distances),
        "maximum_liquidation_cost_erosion_pct": max(liquidation_erosions),
        "liquidation_distance_pct": min(effective_distances),
        "evaluation_notional_usdc": notional,
        "cost_notional_bucket_usdc": cost_bucket,
        "robust_roundtrip_bps": robust_bps,
        "robust_variable_roundtrip_bps": robust_variable_bps,
        "robust_fixed_cost_usdc": robust_fixed_usdc,
    }


def build_artifact(*, campaign_id: str, trace_paths: list[Path],
                   cost_model_path: Path, methodology_path: Path,
                   artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = {**methodology["robustness"],
            "allowed_leverage_grid": methodology["small_account"]["leverage_grid"]}
    cost_model = json.loads(cost_model_path.read_text())
    cost_hash = _sha(cost_model_path)
    evaluated, paths, hashes = {}, {}, {}
    base = artifact_path.resolve().parent
    for path in trace_paths:
        trace = json.loads(path.read_text())
        candidate_id = trace.get("candidate_id")
        metrics = evaluate_trace(trace, gate, cost_model, cost_hash)
        if candidate_id in evaluated:
            raise ValueError("candidate_id de robustesa duplicat")
        evaluated[candidate_id] = metrics
        paths[candidate_id] = _relative(path, base)
        hashes[candidate_id] = _sha(path)
    if not evaluated:
        raise ValueError("Cal almenys un trace de robustesa")
    selected = sorted(key for key, row in evaluated.items()
        if row["monte_carlo_runs"] >= gate["monte_carlo_runs"]
        and row["profitable_monte_carlo_ratio"]
            >= gate["minimum_profitable_monte_carlo_ratio"]
        and row["parameter_variant_count"] >= gate["minimum_parameter_variants"]
        and row["profitable_parameter_variants_ratio"]
            >= gate["minimum_profitable_parameter_variants_ratio"]
        and row["stress_profit_factor"] >= gate["minimum_stress_profit_factor"]
        and row["liquidation_probability"] <= gate["maximum_liquidation_probability"])
    selected_metrics = {key: evaluated[key] for key in selected}
    artifact = {
        "schema_version": 1, "stage": "robustness", "campaign_id": campaign_id,
        "decision": "PASS" if selected else "REJECT", "candidate_ids": selected,
        "holdout_accessed": False, "evidence_class": "observed",
        "parameter_perturbation_pct": gate["parameter_perturbation_pct"],
        "cost_stress_multiplier": gate["cost_stress_multiplier"],
        "evaluated_candidate_robustness_metrics": evaluated,
        "candidate_robustness_metrics": selected_metrics,
        "robustness_trace_paths": paths, "robustness_trace_sha256": hashes,
        "cost_model_path": _relative(cost_model_path, base),
        "cost_model_sha256": cost_hash,
    }
    if selected:
        artifact.update({
            "monte_carlo_runs": min(row["monte_carlo_runs"] for row in selected_metrics.values()),
            "profitable_monte_carlo_ratio": min(
                row["profitable_monte_carlo_ratio"] for row in selected_metrics.values()),
            "minimum_parameter_variant_count": min(
                row["parameter_variant_count"] for row in selected_metrics.values()),
            "profitable_parameter_variants_ratio": min(
                row["profitable_parameter_variants_ratio"] for row in selected_metrics.values()),
            "stress_profit_factor": min(
                row["stress_profit_factor"] for row in selected_metrics.values()),
            "liquidation_probability": max(
                row["liquidation_probability"] for row in selected_metrics.values()),
            "maximum_tested_leverage": min(
                row["tested_leverage"] for row in selected_metrics.values()),
        })
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--trace", action="append", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id, trace_paths=args.trace,
        cost_model_path=args.cost_model,
        methodology_path=args.methodology, artifact_path=args.artifact_output)
    print(json.dumps({"decision": artifact["decision"],
                      "candidate_ids": artifact["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
