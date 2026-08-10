#!/usr/bin/env python3
"""Avalua una sola vegada el holdout final v4 des d'un trace de trades congelat."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def evaluate_trace(trace: dict, scenarios: list[str]) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "final_holdout_trade_trace"):
        raise ValueError("Schema de trace holdout invalid")
    candidate_id = trace.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id holdout absent")
    if trace.get("capital_usdc") != 200:
        raise ValueError("El trace holdout ha d'usar 200 USDC")
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
        values = row.get("net_pnl_usdc_by_cost")
        if not isinstance(values, dict) or set(values) != set(scenarios):
            raise ValueError("Escenaris de cost holdout incomplets")
        for scenario in scenarios:
            value = values[scenario]
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value)):
                raise ValueError("PnL holdout invalid")
            pnl[scenario].append(float(value))
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
        "trades": len(trades),
        "profit_factor_by_cost": profit_factors,
        "net_expectancy_usdc_by_cost": expectancy,
        "drawdown_pct_by_cost": drawdowns,
        "drawdown_pct": max(drawdowns.values()),
    }


def build_artifact(*, campaign_id: str, candidate_id: str, trace_path: Path,
                   methodology_path: Path, artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["final_holdout_validation"]
    metrics = evaluate_trace(json.loads(trace_path.read_text()), gate["cost_scenarios_required"])
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
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = build_artifact(
        campaign_id=args.campaign_id, candidate_id=args.candidate_id,
        trace_path=args.trace, methodology_path=args.methodology,
        artifact_path=args.artifact_output)
    print(json.dumps({key: result[key] for key in (
        "decision", "holdout_trades", "minimum_holdout_profit_factor",
        "holdout_drawdown_pct", "minimum_holdout_net_expectancy_usdc")}, indent=2))


if __name__ == "__main__":
    main()
