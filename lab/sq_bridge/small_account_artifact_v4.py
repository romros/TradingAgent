#!/usr/bin/env python3
"""Avalua i selecciona una candidata v4 per a un compte Ostium de 200 USDC."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from lab.sq_bridge.small_account_trace_v4 import rebuild_from_trace


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _number(value: object, message: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(message)
    return float(value)


def liquidation_distance_pct(leverage: float, venue_max_leverage: float) -> float:
    """Approximate adverse price move using Ostium's published threshold.

    Ostium keeps a 25% collateral backstop at a pair's maximum leverage.
    Lower leverage moves the liquidation threshold towards a total collateral
    loss.  Fees and carry are applied separately by the buffered model below.
    """
    leverage = _number(leverage, "Leverage de liquidacio invalid")
    venue_max_leverage = _number(
        venue_max_leverage, "Limit de leverage de liquidacio invalid")
    if leverage <= 0 or venue_max_leverage <= 0 or leverage > venue_max_leverage:
        raise ValueError("Leverage de liquidacio fora dels limits Ostium")
    loss_threshold_pct = 100.0 - leverage / venue_max_leverage * 25.0
    return loss_threshold_pct / leverage


def liquidation_cost_erosion_pct(roundtrip_bps: float, annual_cost_pct: float,
                                 holding_days: float) -> float:
    """Conservative notional-return erosion before the adverse excursion."""
    return roundtrip_bps / 100.0 + annual_cost_pct * holding_days / 365.25


def cost_buffered_liquidation_distance_pct(
        leverage: float, venue_max_leverage: float, roundtrip_bps: float,
        annual_cost_pct: float, holding_days: float) -> float:
    return max(0.0, liquidation_distance_pct(leverage, venue_max_leverage)
               - liquidation_cost_erosion_pct(
                   roundtrip_bps, annual_cost_pct, holding_days))


def select_cost_envelope(
        cost_model: dict, notional: float) -> tuple[float, dict, dict, dict]:
    """Select a conservative measured bucket without scaling fixed costs.

    The measured variable execution rate may safely come from the next-higher
    notional bucket.  A fixed oracle charge must still be charged in USDC at
    its original amount; converting it to bucket bps and applying those bps to
    a smaller actual notional would undercharge it.
    """
    notional = _number(notional, "Nocional de costos invalid")
    if notional <= 0:
        raise ValueError("Nocional de costos ha de ser positiu")
    if (cost_model.get("decision") != "PASS_COSTS_FROZEN"
            or cost_model.get("costs_frozen") is not True):
        raise ValueError("Model de costos no congelat")
    rows = cost_model.get("by_notional")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("Graella de costos absent")
    available = sorted(float(value) for value in rows)
    bucket = next((value for value in available if value >= notional), None)
    if bucket is None:
        raise ValueError("Nocional fora de la graella de costos mesurada")
    row = rows[format(bucket, "g")]
    scenarios = ("base", "conservative", "stress")
    fixed = row.get("oracle_net_usdc", {})
    if not isinstance(fixed, dict):
        raise ValueError("Costos fixos d'oracle invalids")
    fixed_usdc = {scenario: _number(fixed.get(scenario, 0.0),
                                    f"Cost fix {scenario} invalid")
                  for scenario in scenarios}
    variable_bps = {}
    for scenario in scenarios:
        total = _number(row.get(f"{scenario}_roundtrip_bps"),
                        f"Cost {scenario} absent")
        explicit = row.get(f"{scenario}_variable_roundtrip_bps")
        if explicit is None:
            # Backward-compatible interpretation of already frozen evidence.
            # The total field was expressed at the measured bucket.
            variable = total - fixed_usdc[scenario] / bucket * 10_000
        else:
            variable = _number(explicit, f"Cost variable {scenario} invalid")
            expected_total = variable + fixed_usdc[scenario] / bucket * 10_000
            if not math.isclose(total, expected_total, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f"Descomposicio de cost {scenario} inconsistent")
        if variable < 0:
            raise ValueError(f"Cost variable {scenario} negatiu")
        variable_bps[scenario] = variable
    carry = cost_model.get("carry")
    if not isinstance(carry, dict):
        raise ValueError("Carry de costos absent")
    return bucket, variable_bps, fixed_usdc, carry


def venue_minimum_notional(cost_model: dict) -> float:
    limits = cost_model.get("venue_limits")
    distribution = (limits or {}).get("min_notional_usd")
    if not isinstance(distribution, dict):
        raise ValueError("Minim nocional Ostium absent del model congelat")
    # A strategy must remain executable across every observed snapshot, so use
    # the largest observed venue minimum rather than p50.
    value = _number(distribution.get("max"), "Minim nocional Ostium invalid")
    if value <= 0:
        raise ValueError("Minim nocional Ostium ha de ser positiu")
    return value


def evaluate_trace(trace: dict, gate: dict, robustness_metric: dict,
                   cost_model: dict, expected_cost_hash: str) -> dict:
    schema_version = trace.get("schema_version")
    if (schema_version not in {1, 2}
            or trace.get("trace_type") != "small_account_trade_trace"):
        raise ValueError("Schema de trace de compte petit invalid")
    candidate_id = trace.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id de compte petit absent")
    capital = trace.get("capital_usdc")
    if capital != gate["canonical_capital_usdc"] or trace.get("holdout_accessed") is not False:
        raise ValueError("Compte petit ha d'usar 200 USDC sense obrir holdout")
    if trace.get("stop_loss_required") is not True:
        raise ValueError("Stop loss obligatori")
    risk_pct = _number(trace.get("risk_per_trade_pct"), "Risc per trade invalid")
    if not 0 < risk_pct <= gate["maximum_risk_per_trade_pct"]:
        raise ValueError("Risc fora del contracte")
    fixed_stop_pct = (None if schema_version == 2 else _number(
        trace.get("stop_distance_pct"), "Distancia de stop invalida"))
    if fixed_stop_pct is not None and fixed_stop_pct <= 0:
        raise ValueError("Stop fora del contracte")
    venue_max = _number(trace.get("venue_max_leverage"), "Limit Ostium invalid")
    tested_leverage = _number(
        robustness_metric.get("tested_leverage"), "Envelope de robustesa absent")
    if (venue_max != robustness_metric.get("venue_max_leverage")
            or tested_leverage > venue_max):
        raise ValueError("Envelope Ostium no coincideix amb robustesa")
    if trace.get("cost_model_sha256") != expected_cost_hash:
        raise ValueError("Hash de costos de compte petit no coincideix")

    scenarios = gate["cost_scenarios_required"]
    venue_min_notional = venue_minimum_notional(cost_model)
    trades = trace.get("trades")
    if not isinstance(trades, list) or len(trades) < gate["minimum_trades"]:
        raise ValueError("Trades de compte petit insuficients")
    trade_ids, pnl = [], {scenario: [] for scenario in scenarios}
    liquidation_erosions = []
    notionals, stop_distances, cost_buckets = [], [], []
    cost_bps_rows, variable_bps_rows, fixed_usdc_rows = [], [], []
    for row in trades:
        if not isinstance(row, dict) or not isinstance(row.get("trade_id"), str):
            raise ValueError("Trade de compte petit invalid")
        trade_ids.append(row["trade_id"])
        gross = _number(row.get("gross_return_pct"), "Retorn brut invalid")
        side = row.get("side")
        holding_days = _number(row.get("holding_days"), "Durada de trade invalida")
        if side not in {"long", "short"} or holding_days < 0:
            raise ValueError("Costat o durada de trade invalid")
        stop_pct = _number(
            row.get("initial_stop_distance_pct") if schema_version == 2
            else fixed_stop_pct, "Distancia inicial de stop invalida")
        if stop_pct <= 0:
            raise ValueError("Distancia inicial de stop no positiva")
        notional = capital * risk_pct / stop_pct
        cost_bucket, variable_bps, fixed_usdc, carry = select_cost_envelope(
            cost_model, notional)
        cost_bps = {scenario: variable_bps[scenario]
                    + fixed_usdc[scenario] / notional * 10_000
                    for scenario in variable_bps}
        notionals.append(notional)
        stop_distances.append(stop_pct)
        cost_buckets.append(cost_bucket)
        cost_bps_rows.append(cost_bps)
        variable_bps_rows.append(variable_bps)
        fixed_usdc_rows.append(fixed_usdc)
        stress_annual = _number((carry.get(side) or {}).get(
            "stress_annual_cost_pct"), "Carry stress anual absent")
        liquidation_erosions.append(liquidation_cost_erosion_pct(
            cost_bps["stress"], stress_annual, holding_days))
        for scenario in scenarios:
            annual = _number((carry.get(side) or {}).get(
                f"{scenario}_annual_cost_pct"), "Carry anual absent")
            net_return_pct = (gross - cost_bps[scenario] / 100.0
                              - annual * holding_days / 365.25)
            pnl[scenario].append(notional * net_return_pct / 100.0)
    if trade_ids != sorted(set(trade_ids)):
        raise ValueError("trade_id de compte petit ha de ser unic i ordenat")

    profit_factors, expectancy = {}, {}
    maximum_loss_pct = 0.0
    for scenario, values in pnl.items():
        wins = sum(value for value in values if value > 0)
        losses = -sum(value for value in values if value < 0)
        if losses <= 0:
            raise ValueError(f"Profit factor no estimable: {scenario}")
        profit_factors[scenario] = wins / losses
        expectancy[scenario] = sum(values) / len(values)
        maximum_loss_pct = max(maximum_loss_pct, -min(values) / capital * 100)

    grid = [value for value in gate["leverage_grid"] if value <= venue_max]
    evaluations, safe = {}, []
    worst_liquidation_erosion = max(liquidation_erosions)
    # Reserve the full stress round-trip (including the stress oracle policy)
    # before sizing. This is stricter than the actual entry cash charge and
    # prevents a 200 USDC account from spending its declared reserve on fees.
    for leverage in grid:
        collateral = max(notional / leverage for notional in notionals)
        margin_pct = collateral / capital * 100
        entry_cost_buffer_usdc = max(
            notional * variable["stress"] / 10_000 + fixed["stress"]
            for notional, variable, fixed in zip(
                notionals, variable_bps_rows, fixed_usdc_rows, strict=True))
        capital_committed_usdc = collateral + entry_cost_buffer_usdc
        capital_committed_pct = capital_committed_usdc / capital * 100
        reserve_usdc = capital - capital_committed_usdc
        reserve_pct = reserve_usdc / capital * 100
        nominal_liquidation_distance = liquidation_distance_pct(leverage, venue_max)
        liquidation_distances = [max(
            0.0, nominal_liquidation_distance - erosion)
            for erosion in liquidation_erosions]
        buffers = [distance / stop for distance, stop in zip(
            liquidation_distances, stop_distances, strict=True)]
        liquidation_distance = min(liquidation_distances)
        buffer = min(buffers)
        reasons = []
        if min(notionals) < venue_min_notional:
            reasons.append("position_notional_below_venue_minimum")
        if leverage > tested_leverage:
            reasons.append("exceeds_robustness_tested_leverage")
        if margin_pct > gate["maximum_portfolio_margin_pct"]:
            reasons.append("portfolio_margin_above_limit")
        if reserve_pct < gate["minimum_reserve_pct"]:
            reasons.append("reserve_below_limit")
        if capital_committed_usdc > capital:
            reasons.append("upfront_cash_above_capital")
        if buffer < gate["minimum_stop_to_liquidation_buffer_ratio"]:
            reasons.append("liquidation_buffer_below_limit")
        if maximum_loss_pct > gate["maximum_single_trade_loss_pct"]:
            reasons.append("realized_trade_loss_above_limit")
        evaluations[str(leverage)] = {
            "collateral_usdc": collateral, "portfolio_margin_pct": margin_pct,
            "entry_cost_buffer_usdc": entry_cost_buffer_usdc,
            "capital_committed_usdc": capital_committed_usdc,
            "capital_committed_pct": capital_committed_pct,
            "reserve_usdc": reserve_usdc, "reserve_pct": reserve_pct,
            "nominal_liquidation_distance_pct": nominal_liquidation_distance,
            "liquidation_cost_erosion_pct": worst_liquidation_erosion,
            "liquidation_distance_pct": liquidation_distance,
            "stop_to_liquidation_buffer_ratio": buffer,
            "safe": not reasons, "rejection_reasons": reasons,
        }
        if not reasons:
            safe.append(leverage)
    if not safe:
        selected_leverage = None
        selected = None
    else:
        selected_leverage = max(safe)
        selected = evaluations[str(selected_leverage)]
    higher_rejections = ({str(value): ";".join(evaluations[str(value)]["rejection_reasons"])
                          for value in grid if selected_leverage is not None
                          and value > selected_leverage}
                         if selected_leverage is not None else {})
    return {
        "candidate_id": candidate_id, "trades": len(trades),
        "profit_factor_by_cost": profit_factors,
        "net_expectancy_usdc_by_cost": expectancy,
        "net_profit_factor": min(profit_factors.values()),
        "net_expectancy_usdc": min(expectancy.values()),
        "maximum_single_trade_loss_pct": maximum_loss_pct,
        "risk_per_trade_pct": risk_pct,
        "stop_distance_pct": max(stop_distances),
        "minimum_stop_distance_pct": min(stop_distances),
        "maximum_stop_distance_pct": max(stop_distances),
        "position_notional_usdc": max(notionals),
        "minimum_position_notional_usdc": min(notionals),
        "maximum_position_notional_usdc": max(notionals),
        "venue_minimum_notional_usdc": venue_min_notional,
        "minimum_notional_pass": min(notionals) >= venue_min_notional,
        "venue_max_leverage": venue_max,
        "cost_notional_bucket_usdc": max(cost_buckets),
        "cost_roundtrip_bps_by_scenario": {
            scenario: max(row[scenario] for row in cost_bps_rows)
            for scenario in scenarios},
        "cost_variable_roundtrip_bps_by_scenario": {
            scenario: max(row[scenario] for row in variable_bps_rows)
            for scenario in scenarios},
        "cost_fixed_usdc_by_scenario": {
            scenario: max(row[scenario] for row in fixed_usdc_rows)
            for scenario in scenarios},
        "robustness_tested_leverage": tested_leverage,
        "liquidation_model": gate["liquidation_model"],
        "evaluated_leverage_grid": grid, "leverage_evaluations": evaluations,
        "selected_leverage": selected_leverage,
        "collateral_usdc": selected["collateral_usdc"] if selected else None,
        "entry_cost_buffer_usdc": (
            selected["entry_cost_buffer_usdc"] if selected else None),
        "capital_committed_usdc": (
            selected["capital_committed_usdc"] if selected else None),
        "capital_committed_pct": (
            selected["capital_committed_pct"] if selected else None),
        "reserve_usdc": selected["reserve_usdc"] if selected else None,
        "portfolio_margin_pct": selected["portfolio_margin_pct"] if selected else None,
        "reserve_pct": selected["reserve_pct"] if selected else None,
        "liquidation_distance_pct": selected["liquidation_distance_pct"] if selected else None,
        "nominal_liquidation_distance_pct": (
            selected["nominal_liquidation_distance_pct"] if selected else None),
        "liquidation_cost_erosion_pct": (
            selected["liquidation_cost_erosion_pct"] if selected else None),
        "stop_to_liquidation_buffer_ratio": (
            selected["stop_to_liquidation_buffer_ratio"] if selected else None),
        "higher_leverage_rejection_reasons": higher_rejections,
    }


def build_artifact(*, campaign_id: str, trace_paths: list[Path],
                   robustness_artifact_path: Path, cost_model_path: Path,
                   methodology_path: Path,
                   artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["small_account"]
    robustness = json.loads(robustness_artifact_path.read_text())
    robust_metrics = robustness.get("candidate_robustness_metrics")
    if (robustness.get("stage") != "robustness" or robustness.get("decision") != "PASS"
            or robustness.get("campaign_id") != campaign_id
            or not isinstance(robust_metrics, dict)):
        raise ValueError("Artefacte de robustesa invalid o aliè")
    cost_model = json.loads(cost_model_path.read_text())
    cost_hash = _sha(cost_model_path)
    evaluated, paths, hashes = {}, {}, {}
    base = artifact_path.resolve().parent
    for path in trace_paths:
        trace = json.loads(path.read_text())
        if trace.get("schema_version") == 2 and rebuild_from_trace(trace) != trace:
            raise ValueError("Trace de compte petit no reproduible des de les fonts")
        candidate_id = trace.get("candidate_id")
        if candidate_id not in robust_metrics or candidate_id in evaluated:
            raise ValueError("Filiacio de candidat de compte petit invalida")
        evaluated[candidate_id] = evaluate_trace(
            trace, gate, robust_metrics[candidate_id], cost_model, cost_hash)
        paths[candidate_id] = _relative(path, base)
        hashes[candidate_id] = _sha(path)
    if set(evaluated) != set(robust_metrics):
        raise ValueError("Cal avaluar tots els candidats que superen robustesa")
    passing = {key: row for key, row in evaluated.items()
               if row["selected_leverage"] is not None
               and row["minimum_notional_pass"] is True
               and row["trades"] >= gate["minimum_trades"]
               and row["net_expectancy_usdc"] >= gate["minimum_net_expectancy_usdc"]
               and row["net_profit_factor"] >= gate["minimum_net_profit_factor"]
               and row["maximum_single_trade_loss_pct"]
                   <= gate["maximum_single_trade_loss_pct"]}
    ranked = sorted(passing, key=lambda key: (
        -passing[key]["net_expectancy_usdc"],
        -passing[key]["net_profit_factor"], key))
    selected_id = ranked[0] if ranked else None
    artifact = {
        "schema_version": 1, "stage": "small_account_economics",
        "campaign_id": campaign_id, "decision": "PASS" if selected_id else "REJECT",
        "candidate_ids": [selected_id] if selected_id else [],
        "holdout_accessed": False, "evidence_class": "observed",
        "candidate_selection_policy": gate["candidate_selection_policy"],
        "evaluated_candidate_small_account_metrics": evaluated,
        "small_account_trace_paths": paths, "small_account_trace_sha256": hashes,
        "robustness_artifact_path": _relative(robustness_artifact_path, base),
        "robustness_artifact_sha256": _sha(robustness_artifact_path),
        "cost_model_path": _relative(cost_model_path, base),
        "cost_model_sha256": cost_hash,
    }
    if selected_id:
        row = evaluated[selected_id]
        artifact.update({
            "capital_usdc": gate["canonical_capital_usdc"],
            "net_expectancy_usdc": row["net_expectancy_usdc"],
            "net_profit_factor": row["net_profit_factor"],
            "risk_per_trade_pct": row["risk_per_trade_pct"],
            "portfolio_margin_pct": row["portfolio_margin_pct"],
            "reserve_pct": row["reserve_pct"],
            "selected_leverage": row["selected_leverage"],
            "venue_max_leverage": row["venue_max_leverage"],
            "leverage_selection_policy": gate["leverage_selection_policy"],
            "evaluated_leverage_grid": row["evaluated_leverage_grid"],
            "higher_leverage_rejection_reasons": row["higher_leverage_rejection_reasons"],
            "stop_loss_required": True,
            "position_notional_usdc": row["position_notional_usdc"],
            "minimum_position_notional_usdc": row["minimum_position_notional_usdc"],
            "maximum_position_notional_usdc": row["maximum_position_notional_usdc"],
            "venue_minimum_notional_usdc": row["venue_minimum_notional_usdc"],
            "cost_notional_bucket_usdc": row["cost_notional_bucket_usdc"],
            "cost_roundtrip_bps_by_scenario": row["cost_roundtrip_bps_by_scenario"],
            "cost_variable_roundtrip_bps_by_scenario": (
                row["cost_variable_roundtrip_bps_by_scenario"]),
            "cost_fixed_usdc_by_scenario": row["cost_fixed_usdc_by_scenario"],
            "collateral_usdc": row["collateral_usdc"],
            "entry_cost_buffer_usdc": row["entry_cost_buffer_usdc"],
            "capital_committed_usdc": row["capital_committed_usdc"],
            "capital_committed_pct": row["capital_committed_pct"],
            "reserve_usdc": row["reserve_usdc"],
            "stop_distance_pct": row["stop_distance_pct"],
            "minimum_stop_distance_pct": row["minimum_stop_distance_pct"],
            "maximum_stop_distance_pct": row["maximum_stop_distance_pct"],
            "liquidation_distance_pct": row["liquidation_distance_pct"],
            "stop_to_liquidation_buffer_ratio": row["stop_to_liquidation_buffer_ratio"],
            "nominal_liquidation_distance_pct": row["nominal_liquidation_distance_pct"],
            "liquidation_cost_erosion_pct": row["liquidation_cost_erosion_pct"],
            "liquidation_model": gate["liquidation_model"],
        })
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--trace", action="append", required=True, type=Path)
    parser.add_argument("--robustness-artifact", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id, trace_paths=args.trace,
        robustness_artifact_path=args.robustness_artifact,
        cost_model_path=args.cost_model,
        methodology_path=args.methodology, artifact_path=args.artifact_output)
    print(json.dumps({"decision": artifact["decision"],
                      "candidate_ids": artifact["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
