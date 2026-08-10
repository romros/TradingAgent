#!/usr/bin/env python3
"""Construeix el screen determinista pre-SQ v4 des d'una graella train congelada."""
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


def _number(value: object) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError("PnL del screen invalid")
    return float(value)


def _variant_metrics(variant: dict, scenarios: list[str]) -> dict:
    trades = variant.get("trades")
    if not isinstance(trades, list):
        raise ValueError("Trades de variant absents")
    ids, pnl = [], {scenario: [] for scenario in scenarios}
    for row in trades:
        if not isinstance(row, dict) or not isinstance(row.get("trade_id"), str):
            raise ValueError("Trade del screen invalid")
        ids.append(row["trade_id"])
        values = row.get("net_pnl_usdc_by_cost")
        if not isinstance(values, dict) or set(values) != set(scenarios):
            raise ValueError("Costos del screen incomplets")
        for scenario in scenarios:
            pnl[scenario].append(_number(values[scenario]))
    if ids != sorted(set(ids)):
        raise ValueError("trade_id del screen ha de ser unic i ordenat")
    profit_factors = {}
    for scenario, values in pnl.items():
        wins = sum(value for value in values if value > 0)
        losses = -sum(value for value in values if value < 0)
        if losses <= 0:
            raise ValueError(f"PF train no estimable: {scenario}")
        profit_factors[scenario] = wins / losses
    return {"train_trades": len(trades), "profit_factor_by_cost": profit_factors}


def evaluate_trace(trace: dict, gate: dict) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "hypothesis_screen_grid_trace"):
        raise ValueError("Schema del trace de screen invalid")
    if (trace.get("train_only") is not True
            or trace.get("future_periods_accessed") is not False
            or trace.get("holdout_accessed") is not False):
        raise ValueError("El screen nomes pot veure train")
    cost_hash = trace.get("cost_model_sha256")
    if (not isinstance(cost_hash, str) or len(cost_hash) != 64
            or any(char not in "0123456789abcdef" for char in cost_hash)):
        raise ValueError("Hash de costos del screen invalid")
    hypotheses = trace.get("hypotheses")
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError("Hipotesis del screen absents")
    hypothesis_ids, evaluated, attempted = [], {}, 0
    scenarios = gate["cost_scenarios_required"]
    for hypothesis in hypotheses:
        if (not isinstance(hypothesis, dict)
                or not isinstance(hypothesis.get("hypothesis_id"), str)):
            raise ValueError("Hipotesi del screen invalida")
        hypothesis_id = hypothesis["hypothesis_id"]
        hypothesis_ids.append(hypothesis_id)
        variants = hypothesis.get("variants")
        if not isinstance(variants, list) or not variants:
            raise ValueError("Variants del screen absents")
        variant_ids, metrics = [], {}
        for variant in variants:
            if not isinstance(variant, dict) or not isinstance(variant.get("variant_id"), str):
                raise ValueError("Variant del screen invalida")
            variant_id = variant["variant_id"]
            variant_ids.append(variant_id)
            metrics[variant_id] = _variant_metrics(variant, scenarios)
            attempted += 1
        if variant_ids != sorted(set(variant_ids)):
            raise ValueError("variant_id del screen ha de ser unic i ordenat")
        central_id = hypothesis.get("central_variant_id")
        if central_id not in metrics:
            raise ValueError("Variant central absent")
        if any(
            (variant.get("neighbor_of") is not None if variant["variant_id"] == central_id
             else variant.get("neighbor_of") != central_id)
            for variant in variants):
            raise ValueError("Topologia de veins del screen invalida")
        passing_variants = {key for key, row in metrics.items()
            if row["train_trades"] >= gate["minimum_trades_train"]
            and min(row["profit_factor_by_cost"].values())
                >= gate["minimum_profit_factor_train"]}
        evaluated[hypothesis_id] = {
            **metrics[central_id],
            "stable_neighbor_count": len(passing_variants - {central_id}),
            "central_variant_id": central_id,
            "variant_count": len(variants),
            "central_pass": central_id in passing_variants,
        }
    if hypothesis_ids != sorted(set(hypothesis_ids)):
        raise ValueError("hypothesis_id del screen ha de ser unic i ordenat")
    if attempted > gate["maximum_attempts"]:
        raise ValueError("Pressupost d'intents del screen superat")
    selected = sorted(key for key, row in evaluated.items()
        if row["central_pass"]
        and row["stable_neighbor_count"] >= gate["minimum_stable_neighbors"])
    return {"attempted": attempted, "evaluated_hypothesis_metrics": evaluated,
            "selected_hypothesis_ids": selected}


def build_artifact(*, campaign_id: str, trace_path: Path,
                   methodology_path: Path, artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = methodology["hypothesis_screen"]
    result = evaluate_trace(json.loads(trace_path.read_text()), gate)
    selected = result["selected_hypothesis_ids"]
    evaluated = result["evaluated_hypothesis_metrics"]
    selected_metrics = {key: {
        "train_trades": evaluated[key]["train_trades"],
        "profit_factor_by_cost": evaluated[key]["profit_factor_by_cost"],
        "stable_neighbor_count": evaluated[key]["stable_neighbor_count"],
    } for key in selected}
    artifact = {
        "schema_version": 1, "stage": "hypothesis_screen",
        "campaign_id": campaign_id, "decision": "PASS" if selected else "REJECT",
        "candidate_ids": [], "holdout_accessed": False, "evidence_class": "observed",
        "generator": "deterministic_pre_sq_screen", "attempted": result["attempted"],
        "selected_hypothesis_ids": selected,
        "evaluated_hypothesis_metrics": evaluated,
        "selected_hypothesis_metrics": selected_metrics,
        "applied_cost_scenarios": gate["cost_scenarios_required"],
        "all_cost_scenarios_applied": True, "train_only": True,
        "future_periods_accessed": False,
        "hypothesis_screen_trace_path": _relative(trace_path, artifact_path.resolve().parent),
        "hypothesis_screen_trace_sha256": _sha(trace_path),
    }
    if selected:
        artifact.update({
            "minimum_selected_train_trades": min(
                row["train_trades"] for row in selected_metrics.values()),
            "minimum_selected_train_profit_factor": min(
                min(row["profit_factor_by_cost"].values())
                for row in selected_metrics.values()),
            "minimum_selected_stable_neighbors": min(
                row["stable_neighbor_count"] for row in selected_metrics.values()),
            "stable_region_pass": True,
        })
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id, trace_path=args.trace,
        methodology_path=args.methodology, artifact_path=args.artifact_output)
    print(json.dumps({"decision": artifact["decision"],
                      "selected_hypothesis_ids": artifact["selected_hypothesis_ids"]}, indent=2))


if __name__ == "__main__":
    main()
