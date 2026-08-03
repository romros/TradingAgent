#!/usr/bin/env python3
"""Independent validation of frozen BTC v12 topology representatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import load_m1, metrics, simulate
from lab.sq_bridge.btc_regime_breakout_v12 import regime_frames


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(source: Path, config: dict, development: dict) -> dict:
    if development["family_id"] != config["family_id"] or development["config_sha256"] != canonical_hash(config):
        raise ValueError("DEVELOPMENT_CONFIG_LINEAGE_MISMATCH")
    if development["source_sha256"] != file_sha256(source):
        raise ValueError("DEVELOPMENT_SOURCE_LINEAGE_MISMATCH")
    selected = development["topology_selected_representatives"]
    start, end = config["periods"]["validation_from"], config["periods"]["validation_to"]
    warmup = (pd.Timestamp(start) - pd.Timedelta(days=300)).date().isoformat()
    raw = load_m1(source, warmup, end); timeframes = sorted({item["timeframe"] for item in selected})
    frames = regime_frames(raw, timeframes); gate = config["pre_registered_validation_gate"]
    dev_by_id = {row["candidate_id"]: row for row in development["passing_candidates"]}; results = []
    for item in selected:
        trades = simulate(frames[item["timeframe"]], item["mechanism"], item["parameters"], config["cost_model"], start, end)
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        dev_ev = dev_by_id[item["candidate_id"]]["metrics"]["stress"]["expectancy_bps"]
        decay = 100 * (dev_ev - stress["expectancy_bps"]) / abs(dev_ev) if dev_ev else 999
        passed = stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_quarter_ratio"] >= gate["minimum_positive_quarter_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"] and decay <= gate["maximum_development_validation_expectancy_decay_pct"]
        results.append({**item, "metrics": measured, "development_validation_expectancy_decay_pct": decay,
                        "decision": "PASS" if passed else "REJECT"})
    passing = [item["candidate_id"] for item in results if item["decision"] == "PASS"]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "validation",
            "development_artifact_sha256": canonical_hash(development), "source_sha256": development["source_sha256"],
            "candidates_evaluated": len(results), "results": results, "passing_candidate_ids": passing,
            "decision": "PASS_VALIDATION" if passing else "REJECT_TEMPORAL_VALIDATION",
            "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run(args.source, json.loads(args.family.read_text()), json.loads(args.development.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "passing_candidate_ids": result["passing_candidate_ids"],
                      "oos_accessed": False, "holdout_accessed": False}, indent=2))


if __name__ == "__main__": main()
