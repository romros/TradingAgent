#!/usr/bin/env python3
"""Independent validation of frozen v18 topology representatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import metrics
from lab.sq_bridge.crypto_intraday_compression_v18 import hourly, simulate, trade_diagnostics


def run(sources: dict[str, Path], config: dict, development: dict) -> dict:
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    source_hashes = {asset: file_sha256(path) for asset, path in sources.items()}
    if development["config_sha256"] != config_hash or development["source_sha256"] != source_hashes:
        raise ValueError("DEVELOPMENT_LINEAGE_MISMATCH")
    representatives = development["topology_selected_representatives"]
    if not representatives:
        raise ValueError("NO_STABLE_DEVELOPMENT_REPRESENTATIVE")
    validation_start, validation_end = config["periods"]["validation_from"], config["periods"]["validation_to"]
    warmup_start = str((pd.Timestamp(validation_start) - pd.Timedelta(days=21)).date())
    frames = {asset: hourly(path, warmup_start, validation_end) for asset, path in sources.items()}
    gate, rows = config["pre_registered_validation_gate"], []
    by_id = {row["candidate_id"]: row for row in development["passing_candidates"]}
    for representative in representatives:
        candidate = representative["candidate_id"]; params = representative["parameters"]
        trades = simulate(frames[params["asset"]], params, config["cost_model"], config["small_account"], validation_start, validation_end)
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        liquidations = sum(trade["liquidation"] for trade in trades)
        expectancy_usdc = stress["expectancy_bps"] / 10_000 * config["small_account"]["capital_usdc"]
        development_ev = by_id[candidate]["metrics"]["stress"]["expectancy_bps"]
        decay = (development_ev - stress["expectancy_bps"]) / abs(development_ev) * 100 if development_ev else 999.0
        passed = (stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
            and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
            and stress["positive_quarter_ratio"] >= gate["minimum_positive_quarter_ratio"]
            and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
            and liquidations <= gate["maximum_liquidations"]
            and decay <= gate["maximum_development_validation_expectancy_decay_pct"])
        rows.append({"candidate_id": candidate, "parameters": params, "metrics": measured,
            "liquidations": liquidations, "stress_expectancy_usdc": expectancy_usdc,
            "development_validation_expectancy_decay_pct": decay, "trade_diagnostics": trade_diagnostics(trades),
            "passes_validation_gate": bool(passed)})
    passing = [row["candidate_id"] for row in rows if row["passes_validation_gate"]]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "validation",
        "source_sha256": source_hashes, "config_sha256": config_hash,
        "development_canonical_content_sha256": hashlib.sha256(json.dumps(development, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "validation_from": validation_start, "validation_to": validation_end, "results": rows,
        "passing_candidate_ids": passing,
        "decision": "PASS_TEMPORAL_VALIDATION" if passing else "REJECT_TEMPORAL_VALIDATION",
        "holdout_accessed": False, "sqcli_builder_executed": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--development", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, json.loads(args.family.read_text()), json.loads(args.development.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "passing_candidate_ids": result["passing_candidate_ids"], "results": result["results"], "holdout_accessed": False}, indent=2))


if __name__ == "__main__": main()
