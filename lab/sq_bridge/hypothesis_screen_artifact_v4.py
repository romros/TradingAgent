#!/usr/bin/env python3
"""Construeix el screen determinista pre-SQ v4 des d'una graella train congelada."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path

from lab.sq_bridge.small_account_artifact_v4 import select_cost_envelope
from lab.sq_bridge.temporal_split_contract_v4 import digest as temporal_contract_digest
from lab.sq_bridge.eurusd_d1_hypothesis_trace_v4 import (
    PRODUCER_ID as EURUSD_D1_PRODUCER_ID,
    replay_matches as replay_eurusd_d1,
)


SOURCE_TRADE_REPLAY_VERIFIERS = {
    EURUSD_D1_PRODUCER_ID: replay_eurusd_d1,
}


def verify_source_trade_replay(trace: dict) -> bool:
    verifier = SOURCE_TRADE_REPLAY_VERIFIERS.get(trace.get("producer_id"))
    return verifier is not None and verifier(trace)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _number(value: object) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError("PnL del screen invalid")
    return float(value)


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("+00:00"):
        raise ValueError(f"Timestamp {label} no UTC")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Timestamp {label} invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"Timestamp {label} no UTC")
    return parsed


def _validate_source_lineage(trace: dict, temporal_split: dict) -> datetime:
    path_value = trace.get("source_path")
    if not isinstance(path_value, str) or not Path(path_value).is_absolute():
        raise ValueError("Font canonica del screen ha de ser absoluta")
    path = Path(path_value)
    if not path.is_file() or trace.get("source_sha256") != _sha(path):
        raise ValueError("Hash de la font canonica del screen no coincideix")
    lines = path.read_text().splitlines()
    source_rows = trace.get("source_rows")
    train_rows = trace.get("train_rows")
    expected_train = math.floor(len(lines) * temporal_split["train_pct"] / 100)
    contract = trace.get("temporal_contract")
    if (not isinstance(contract, dict)
            or trace.get("temporal_contract_sha256") != temporal_contract_digest(contract)
            or contract.get("source_sha256") != trace.get("source_sha256")
            or contract.get("source_rows") != len(lines)
            or contract.get("segments", {}).get("train", {}).get("last_row_index")
                != expected_train - 1
            or contract.get("segments", {}).get("train", {}).get("to")
                != lines[expected_train - 1].split(",", 1)[0].replace(".", "-")
            or contract.get("percentages") != {
                name: temporal_split[f"{name}_pct"] for name in (
                    "train", "validation", "oos", "final_holdout")}
            or contract.get("embargo_bars_before_each_post_train_segment")
                != temporal_split["embargo_bars"]):
        raise ValueError("Contracte posicional del screen invalid")
    if (source_rows != len(lines) or train_rows != expected_train
            or trace.get("temporal_split") != temporal_split or expected_train < 1):
        raise ValueError("Tall train del screen no coincideix amb metodologia")
    first = lines[0].split(",", 1)[0].replace(".", "-")
    train_end = lines[expected_train - 1].split(",", 1)[0].replace(".", "-")
    if (trace.get("source_first_utc") != f"{first}T00:00:00+00:00"
            or trace.get("train_end_utc") != f"{train_end}T00:00:00+00:00"):
        raise ValueError("Fronteres temporals del screen no coincideixen amb la font")
    return _utc(trace["train_end_utc"], "final train")


def _variant_metrics(variant: dict, scenarios: list[str], notional: float,
                     cost_bps: dict, carry: dict, train_end: datetime) -> dict:
    trades = variant.get("trades")
    if not isinstance(trades, list):
        raise ValueError("Trades de variant absents")
    ids, pnl, previous_exit = [], {scenario: [] for scenario in scenarios}, None
    for row in trades:
        if not isinstance(row, dict) or not isinstance(row.get("trade_id"), str):
            raise ValueError("Trade del screen invalid")
        ids.append(row["trade_id"])
        entry = _utc(row.get("entry_timestamp"), "entrada screen")
        exit_ = _utc(row.get("exit_timestamp"), "sortida screen")
        if exit_ < entry or exit_ > train_end or (previous_exit and entry < previous_exit):
            raise ValueError("Trade del screen fora de train o solapat")
        previous_exit = exit_
        gross = _number(row.get("gross_return_pct"))
        side, holding_days = row.get("side"), _number(row.get("holding_days"))
        if side not in {"long", "short"} or holding_days < 0:
            raise ValueError("Costat o durada del screen invalid")
        for scenario in scenarios:
            annual = _number((carry.get(side) or {}).get(
                f"{scenario}_annual_cost_pct"))
            net_pct = gross - cost_bps[scenario] / 100 - annual * holding_days / 365.25
            pnl[scenario].append(notional * net_pct / 100)
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


def evaluate_trace(trace: dict, gate: dict, cost_model: dict,
                   expected_cost_hash: str) -> dict:
    if (trace.get("schema_version") != 1
            or trace.get("trace_type") != "hypothesis_screen_grid_trace"):
        raise ValueError("Schema del trace de screen invalid")
    if (trace.get("train_only") is not True
            or trace.get("future_periods_accessed") is not False
            or trace.get("holdout_accessed") is not False):
        raise ValueError("El screen nomes pot veure train")
    if trace.get("cost_model_sha256") != expected_cost_hash:
        raise ValueError("Hash de costos del screen no coincideix")
    temporal_split = gate.get("temporal_split")
    if not isinstance(temporal_split, dict):
        raise ValueError("Split temporal del screen absent")
    train_end = _validate_source_lineage(trace, temporal_split)
    notional = _number(trace.get("screen_notional_usdc"))
    if notional != gate["screen_notional_usdc"]:
        raise ValueError("Nocional canonic del screen invalid")
    cost_bucket, variable_bps, fixed_usdc, carry = select_cost_envelope(
        cost_model, notional)
    cost_bps = {scenario: variable_bps[scenario]
                + fixed_usdc[scenario] / notional * 10_000
                for scenario in variable_bps}
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
            metrics[variant_id] = _variant_metrics(
                variant, scenarios, notional, cost_bps, carry, train_end)
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
            "screen_notional_usdc": notional,
            "cost_notional_bucket_usdc": cost_bucket,
            "cost_roundtrip_bps_by_scenario": cost_bps,
            "cost_variable_roundtrip_bps_by_scenario": variable_bps,
            "cost_fixed_usdc_by_scenario": fixed_usdc,
            "selected_hypothesis_ids": selected}


def build_artifact(*, campaign_id: str, trace_path: Path,
                   cost_model_path: Path, methodology_path: Path,
                   artifact_path: Path) -> dict:
    methodology = json.loads(methodology_path.read_text())
    gate = {**methodology["hypothesis_screen"],
            "temporal_split": methodology["temporal_split"]}
    cost_model = json.loads(cost_model_path.read_text())
    cost_hash = _sha(cost_model_path)
    trace = json.loads(trace_path.read_text())
    result = evaluate_trace(trace, gate,
                            cost_model, cost_hash)
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
        "producer_id": trace.get("producer_id"),
        "source_trade_replay_verified": verify_source_trade_replay(trace),
        "selected_hypothesis_ids": selected,
        "evaluated_hypothesis_metrics": evaluated,
        "selected_hypothesis_metrics": selected_metrics,
        "applied_cost_scenarios": gate["cost_scenarios_required"],
        "all_cost_scenarios_applied": True, "train_only": True,
        "future_periods_accessed": False,
        "screen_notional_usdc": result["screen_notional_usdc"],
        "cost_notional_bucket_usdc": result["cost_notional_bucket_usdc"],
        "cost_roundtrip_bps_by_scenario": result["cost_roundtrip_bps_by_scenario"],
        "cost_variable_roundtrip_bps_by_scenario": (
            result["cost_variable_roundtrip_bps_by_scenario"]),
        "cost_fixed_usdc_by_scenario": result["cost_fixed_usdc_by_scenario"],
        "cost_model_path": _relative(cost_model_path, artifact_path.resolve().parent),
        "cost_model_sha256": cost_hash,
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
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    artifact = build_artifact(
        campaign_id=args.campaign_id, trace_path=args.trace,
        cost_model_path=args.cost_model,
        methodology_path=args.methodology, artifact_path=args.artifact_output)
    print(json.dumps({"decision": artifact["decision"],
                      "selected_hypothesis_ids": artifact["selected_hypothesis_ids"]}, indent=2))


if __name__ == "__main__":
    main()
