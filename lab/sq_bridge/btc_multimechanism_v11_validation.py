#!/usr/bin/env python3
"""Validate topology-selected BTC v11 representatives without OOS/holdout access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import aggregate, enrich, load_m1, metrics, simulate


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(source: Path, config: dict, train: dict) -> dict:
    if train["family_id"] != config["family_id"] or train["config_sha256"] != canonical_hash(config):
        raise ValueError("TRAIN_CONFIG_LINEAGE_MISMATCH")
    if train["source_sha256"] != file_sha256(source):
        raise ValueError("TRAIN_SOURCE_LINEAGE_MISMATCH")
    selected = train["topology_selected_representatives"]
    start, end = config["periods"]["validation_from"], config["periods"]["validation_to"]
    warmup = (pd.Timestamp(start) - pd.Timedelta(days=300)).date().isoformat()
    raw = load_m1(source, warmup, end)
    timeframes = sorted({item["timeframe"] for item in selected})
    frames = {timeframe: enrich(aggregate(raw, timeframe)) for timeframe in timeframes}
    gate = config["pre_registered_validation_gate"]; results = []
    train_by_id = {row["candidate_id"]: row for row in train["passing_candidates"]}
    for item in selected:
        trades = simulate(frames[item["timeframe"]], item["mechanism"], item["parameters"], config["cost_model"], start, end)
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}
        stress = measured["stress"]; train_ev = train_by_id[item["candidate_id"]]["metrics"]["stress"]["expectancy_bps"]
        decay = 100 * (train_ev - stress["expectancy_bps"]) / abs(train_ev) if train_ev else 999
        passed = stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_half_year_ratio"] >= gate["minimum_positive_half_year_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"] and decay <= gate["maximum_train_validation_expectancy_decay_pct"]
        results.append({**item, "metrics": measured, "train_validation_expectancy_decay_pct": decay,
                        "decision": "PASS" if passed else "REJECT"})
    passing = [item["candidate_id"] for item in results if item["decision"] == "PASS"]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "validation",
            "train_artifact_sha256": canonical_hash(train), "source_sha256": train["source_sha256"],
            "coverage": {tf: {"from": frame.index.min().isoformat(), "to": frame.index.max().isoformat(), "bars_with_warmup": len(frame)} for tf, frame in frames.items()},
            "selection_rule": config["selection"]["rule"], "candidates_evaluated": len(results),
            "results": results, "passing_candidate_ids": passing,
            "decision": "PASS_VALIDATION" if passing else "REJECT_TEMPORAL_VALIDATION",
            "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False,
            "paper_or_live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run(args.source, json.loads(args.family.read_text()), json.loads(args.train.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "candidates_evaluated": result["candidates_evaluated"],
                      "passing_candidate_ids": result["passing_candidate_ids"], "oos_accessed": False, "holdout_accessed": False}, indent=2))


if __name__ == "__main__": main()
