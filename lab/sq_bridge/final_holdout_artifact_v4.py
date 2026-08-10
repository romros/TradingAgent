#!/usr/bin/env python3
"""Avalua una sola vegada el holdout final v4 des d'un trace de trades congelat."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from lab.sq_bridge.small_account_artifact_v4 import select_cost_envelope


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def evaluate_trace(trace: dict, scenarios: list[str], cost_model: dict,
                   expected_cost_hash: str, sizing: dict,
                   expected_sizing_hash: str) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "final_holdout_trade_trace"):
        raise ValueError("Schema de trace holdout invalid")
    candidate_id = trace.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id holdout absent")
    if trace.get("capital_usdc") != 200:
        raise ValueError("El trace holdout ha d'usar 200 USDC")
    if (trace.get("cost_model_sha256") != expected_cost_hash
            or trace.get("small_account_artifact_sha256") != expected_sizing_hash):
        raise ValueError("Fonts congelades del holdout no coincideixen")
    notional = sizing.get("position_notional_usdc")
    leverage = sizing.get("selected_leverage")
    if (trace.get("position_notional_usdc") != notional
            or trace.get("selected_leverage") != leverage
            or not isinstance(notional, (int, float)) or isinstance(notional, bool)
            or notional <= 0 or not isinstance(leverage, (int, float))
            or isinstance(leverage, bool) or leverage <= 0):
        raise ValueError("Sizing del holdout diferent del compte petit congelat")
    cost_bucket, variable_bps, fixed_usdc, carry = select_cost_envelope(
        cost_model, float(notional))
    cost_bps = {scenario: variable_bps[scenario]
                + fixed_usdc[scenario] / float(notional) * 10_000
                for scenario in variable_bps}
    if trace.get("selection_frozen_before_holdout") is not True:
        raise ValueError("Seleccio no congelada abans del holdout")
    if trace.get("parameters_changed_after_holdout") is not False:
        raise ValueError("Parametres canviats despres d'obrir holdout")
    if trace.get("holdout_evaluation_count") != 1:
        raise ValueError("El holdout nomes es pot avaluar una vegada")
    trades = trace.get("trades")
    if not isinstance(trades, list):
        raise ValueError("Trades holdout absents")
    ids, pnl = [], {scenario: [] for scenario in scenarios}
    for row in trades:
        if not isinstance(row, dict) or not isinstance(row.get("trade_id"), str):
            raise ValueError("Trade holdout invalid")
        ids.append(row["trade_id"])
        gross, side, days = row.get("gross_return_pct"), row.get("side"), row.get("holding_days")
        if (not isinstance(gross, (int, float)) or isinstance(gross, bool)
                or not math.isfinite(gross) or side not in {"long", "short"}
                or not isinstance(days, (int, float)) or isinstance(days, bool)
                or not math.isfinite(days) or days < 0):
            raise ValueError("Retorn brut, costat o durada holdout invalid")
        for scenario in scenarios:
            annual = (carry.get(side) or {}).get(f"{scenario}_annual_cost_pct")
            if (not isinstance(annual, (int, float)) or isinstance(annual, bool)
                    or not math.isfinite(annual)):
                raise ValueError("Carry holdout absent")
            net_pct = (float(gross) - cost_bps[scenario] / 100
                       - float(annual) * float(days) / 365.25)
            pnl[scenario].append(float(notional) * net_pct / 100)
    if ids != sorted(set(ids)):
        raise ValueError("trade_id holdout ha de ser unic i ordenat")
    profit_factors, expectancy, drawdowns = {}, {}, {}
    for scenario, values in pnl.items():
        wins = sum(value for value in values if value > 0)
        losses = -sum(value for value in values if value < 0)
        if not values or losses <= 0:
            raise ValueError(f"PF no estimable al holdout: {scenario}")
        profit_factors[scenario] = wins / losses
        expectancy[scenario] = sum(values) / len(values)
        equity = peak = 200.0
        maximum_drawdown = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak * 100)
        drawdowns[scenario] = maximum_drawdown
    return {
        "candidate_id": candidate_id,
        "position_notional_usdc": notional,
        "selected_leverage": leverage,
        "cost_notional_bucket_usdc": cost_bucket,
        "cost_roundtrip_bps_by_scenario": cost_bps,
        "cost_variable_roundtrip_bps_by_scenario": variable_bps,
        "cost_fixed_usdc_by_scenario": fixed_usdc,
        "trades": len(trades),
        "profit_factor_by_cost": profit_factors,
        "net_expectancy_usdc_by_cost": expectancy,
        "drawdown_pct_by_cost": drawdowns,
        "drawdown_pct": max(drawdowns.values()),
    }


def build_artifact(*, campaign_id: str, candidate_id: str, trace_path: Path,
                   small_account_artifact_path: Path, cost_model_path: Path,
                   methodology_path: Path, artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["final_holdout_validation"]
    sizing = json.loads(small_account_artifact_path.read_text())
    if (sizing.get("stage") != "small_account_economics"
            or sizing.get("decision") != "PASS"
            or sizing.get("campaign_id") != campaign_id
            or sizing.get("candidate_ids") != [candidate_id]):
        raise ValueError("Artefacte de compte petit no congela aquest candidat")
    cost_model = json.loads(cost_model_path.read_text())
    cost_hash, sizing_hash = _sha(cost_model_path), _sha(small_account_artifact_path)
    if sizing.get("cost_model_sha256") != cost_hash:
        raise ValueError("Compte petit i holdout no comparteixen costos")
    metrics = evaluate_trace(
        json.loads(trace_path.read_text()), gate["cost_scenarios_required"],
        cost_model, cost_hash, sizing, sizing_hash)
    if metrics["candidate_id"] != candidate_id:
        raise ValueError("Candidate lineage mismatch al holdout")
    minimum_pf = min(metrics["profit_factor_by_cost"].values())
    minimum_expectancy = min(metrics["net_expectancy_usdc_by_cost"].values())
    passed = (metrics["trades"] >= gate["minimum_trades"]
              and minimum_pf >= gate["minimum_profit_factor"]
              and metrics["drawdown_pct"] <= gate["maximum_drawdown_pct"]
              and minimum_expectancy >= gate["minimum_net_expectancy_usdc"])
    base = artifact_path.resolve().parent
    artifact = {
        "schema_version": 1, "stage": "final_holdout_validation",
        "campaign_id": campaign_id, "decision": "PASS" if passed else "REJECT",
        "candidate_ids": [candidate_id], "holdout_accessed": True,
        "evidence_class": "observed", "selection_frozen_before_holdout": True,
        "holdout_evaluation_count": 1, "parameters_changed_after_holdout": False,
        "candidate_holdout_metrics": {candidate_id: metrics},
        "holdout_trades": metrics["trades"],
        "minimum_holdout_profit_factor": minimum_pf,
        "holdout_drawdown_pct": metrics["drawdown_pct"],
        "minimum_holdout_net_expectancy_usdc": minimum_expectancy,
        "applied_cost_scenarios": gate["cost_scenarios_required"],
        "holdout_trace_path": _relative(trace_path, base),
        "holdout_trace_sha256": _sha(trace_path),
        "small_account_artifact_path": _relative(small_account_artifact_path, base),
        "small_account_artifact_sha256": sizing_hash,
        "cost_model_path": _relative(cost_model_path, base),
        "cost_model_sha256": cost_hash,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--small-account-artifact", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = build_artifact(
        campaign_id=args.campaign_id, candidate_id=args.candidate_id,
        trace_path=args.trace, small_account_artifact_path=args.small_account_artifact,
        cost_model_path=args.cost_model, methodology_path=args.methodology,
        artifact_path=args.artifact_output)
    print(json.dumps({key: result[key] for key in (
        "decision", "holdout_trades", "minimum_holdout_profit_factor",
        "holdout_drawdown_pct", "minimum_holdout_net_expectancy_usdc")}, indent=2))


if __name__ == "__main__":
    main()
