#!/usr/bin/env python3
"""Independent temporal validation of a frozen crypto relative-momentum representative."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import metrics
from lab.sq_bridge.crypto_relative_momentum_v15 import daily, simulate


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(sources: dict[str, Path], config: dict, development: dict) -> dict:
    if development["family_id"] != config["family_id"] or development["config_sha256"] != canonical_hash(config):
        raise ValueError("DEVELOPMENT_CONFIG_LINEAGE_MISMATCH")
    hashes = {asset: file_sha256(path) for asset, path in sources.items()}
    if hashes != development["source_sha256"]: raise ValueError("DEVELOPMENT_SOURCE_LINEAGE_MISMATCH")
    selected = development["topology_selected_representatives"]
    start, end = config["periods"]["validation_from"], config["periods"]["validation_to"]
    warmup = (pd.Timestamp(start) - pd.Timedelta(days=180)).date().isoformat()
    periods = tuple(config["grid"]["volatility_lookback_days"])
    frames = {asset: daily(path, warmup, end, periods) for asset, path in sources.items()}
    dev_by_id = {item["candidate_id"]: item for item in development["passing_candidates"]}; gate = config["pre_registered_validation_gate"]; results = []
    for selected_item in selected:
        trades = simulate(frames, selected_item["parameters"], config["cost_model"], config["small_account"], start, end)
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        dev_ev = dev_by_id[selected_item["candidate_id"]]["metrics"]["stress"]["expectancy_bps"]
        decay = 100 * (dev_ev - stress["expectancy_bps"]) / abs(dev_ev) if dev_ev else 999
        passed = stress["trades"] >= gate["minimum_portfolio_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_quarter_ratio"] >= gate["minimum_positive_quarter_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"] and decay <= gate["maximum_development_validation_expectancy_decay_pct"]
        results.append({**selected_item, "metrics": measured, "development_validation_expectancy_decay_pct": decay,
                        "decision": "PASS" if passed else "REJECT"})
    passing = [item["candidate_id"] for item in results if item["decision"] == "PASS"]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "validation",
            "development_artifact_sha256": canonical_hash(development), "source_sha256": hashes,
            "candidates_evaluated": len(results), "results": results, "passing_candidate_ids": passing,
            "decision": "PASS_VALIDATION" if passing else "REJECT_TEMPORAL_VALIDATION",
            "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--development", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, json.loads(args.family.read_text()), json.loads(args.development.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "passing_candidate_ids": result["passing_candidate_ids"], "oos_accessed": False, "holdout_accessed": False}, indent=2))


if __name__ == "__main__": main()
