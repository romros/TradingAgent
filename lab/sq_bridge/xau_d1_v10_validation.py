#!/usr/bin/env python3
"""Evaluate only the topology-frozen v10 representative on validation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.xau_d1_inside_breakout_v9 import load_daily, metrics
from lab.sq_bridge.xau_d1_trend_pullback_v10 import enrich, simulate


def passes_gate(scenarios: dict, train_ev: float, gate: dict) -> tuple[bool, float]:
    validation_ev = scenarios["stress"]["expectancy_bps"]
    decay = 100 * (train_ev - validation_ev) / train_ev if train_ev > 0 else 999
    passed = bool(scenarios["stress"]["trades"] >= gate["minimum_trades"] and
                  scenarios["stress"]["profit_factor"] >= gate["minimum_stress_profit_factor"] and
                  scenarios["stress"]["net_return_pct"] > gate["minimum_stress_net_return_pct"] and
                  scenarios["stress"]["positive_year_ratio"] >= gate["minimum_positive_year_ratio"] and
                  scenarios["stress"]["max_drawdown_pct"] <= gate["maximum_stress_drawdown_pct"] and
                  decay <= gate["maximum_train_validation_expectancy_decay_pct"])
    return passed, decay


def validate(root: Path, family: dict, selection: dict) -> dict:
    if selection.get("validation_accessed") or selection.get("holdout_accessed"):
        raise ValueError("SELECTION_ARTIFACT_ALREADY_UNSEALED")
    start, end = family["periods"]["validation_from"], family["periods"]["validation_to"]
    warmup = str((pd.Timestamp(start) - pd.Timedelta(days=400)).date())
    enriched = enrich(load_daily(root, warmup, end))
    frame = enriched.loc[start:end]
    gate = family["pre_registered_validation_gate"]
    results = []
    for selected in selection["selected"]:
        trades = simulate(frame, selected["parameters"], family["costs"])
        scenarios = {name: metrics(trades, name) for name in family["costs"]}
        train_ev = selected["train_metrics"]["stress"]["expectancy_bps"]
        passed, decay = passes_gate(scenarios, train_ev, gate)
        results.append({"candidate_id": selected["candidate_id"], "parameters": selected["parameters"],
                        "metrics": scenarios, "stress_expectancy_decay_pct": round(decay, 6), "passes": passed})
    passing = [row["candidate_id"] for row in results if row["passes"]]
    return {
        "schema_version": 1, "family_id": family["family_id"], "period": "validation",
        "coverage": {"from": str(frame.index.min().date()), "to": str(frame.index.max().date()), "sessions": len(frame)},
        "selected_candidate_ids": selection["selected_candidate_ids"], "passing_candidate_ids": passing,
        "decision": "PASS" if len(passing) == len(results) else "REJECT",
        "results": results, "oos_accessed": False, "holdout_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.root, json.loads(args.family.read_text()), json.loads(args.selection.read_text()))
    result["selection_artifact"] = str(args.selection)
    result["selection_artifact_sha256"] = hashlib.sha256(args.selection.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
