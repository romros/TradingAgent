#!/usr/bin/env python3
"""Internal, explicitly non-independent walk-forward for frozen v19 representatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import metrics
from lab.sq_bridge.crypto_capitulation_reclaim_v19 import reclaim_signals, simulate
from lab.sq_bridge.crypto_intraday_compression_v18 import hourly, trade_diagnostics


def canonical_sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def run(sources: dict[str, Path], config: dict, temporal_gate: dict, discovery: dict) -> dict:
    if temporal_gate["decision"] != "PASS_INTERNAL_NON_INDEPENDENT" or temporal_gate["performance_promotion_authorized"]:
        raise ValueError("TEMPORAL_GATE_NOT_INTERNAL_SAFE")
    config_hash, source_hashes = canonical_sha(config), {asset: file_sha256(path) for asset, path in sources.items()}
    if discovery["config_sha256"] != config_hash or discovery["source_sha256"] != source_hashes:
        raise ValueError("DISCOVERY_LINEAGE_MISMATCH")
    if discovery["temporal_gate_sha256"] != canonical_sha(temporal_gate):
        raise ValueError("TEMPORAL_GATE_LINEAGE_MISMATCH")
    representatives = discovery["topology_selected_representatives"]
    if not representatives: raise ValueError("NO_STABLE_DISCOVERY_REPRESENTATIVE")
    folds = config["periods"]["internal_folds"]
    warmup = str((pd.Timestamp(folds[0]["from"]) - pd.Timedelta(days=21)).date())
    frames = {asset: hourly(path, warmup, folds[-1]["to"]) for asset, path in sources.items()}
    discovery_rows = {row["candidate_id"]: row for row in discovery["passing_candidates"]}; gate = config["pre_registered_internal_walk_forward_gate"]
    rows = []
    for representative in representatives:
        candidate, params = representative["candidate_id"], representative["parameters"]
        frame = frames[params["asset"]]; prepared = reclaim_signals(frame, params); all_trades, fold_rows = [], []
        for fold in folds:
            trades = simulate(frame, params, config["cost_model"], config["small_account"], fold["from"], fold["to"], prepared)
            measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}
            fold_rows.append({"fold_id": fold["id"], "from": fold["from"], "to": fold["to"], "metrics": measured,
                "trade_diagnostics": trade_diagnostics(trades), "positive_stress": measured["stress"]["net_return_pct"] > 0})
            all_trades.extend(trades)
        aggregate = {name: metrics(all_trades, name) for name in config["cost_model"]["scenarios"]}; stress = aggregate["stress"]
        liquidations = sum(trade["liquidation"] for trade in all_trades); positive_ratio = sum(row["positive_stress"] for row in fold_rows) / len(fold_rows)
        discovery_ev = discovery_rows[candidate]["metrics"]["stress"]["expectancy_bps"]
        decay = (discovery_ev - stress["expectancy_bps"]) / abs(discovery_ev) * 100 if discovery_ev else 999.0
        passed = (stress["trades"] >= gate["minimum_total_trades"] and min(row["metrics"]["stress"]["trades"] for row in fold_rows) >= gate["minimum_trades_per_fold"]
            and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
            and positive_ratio >= gate["minimum_positive_fold_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
            and liquidations <= gate["maximum_liquidations"] and decay <= gate["maximum_discovery_walk_forward_expectancy_decay_pct"])
        rows.append({"candidate_id": candidate, "parameters": params, "folds": fold_rows, "aggregate_metrics": aggregate,
            "aggregate_trade_diagnostics": trade_diagnostics(all_trades), "positive_fold_ratio": positive_ratio,
            "liquidations": liquidations, "discovery_walk_forward_expectancy_decay_pct": decay,
            "passes_internal_walk_forward_gate": bool(passed)})
    passing = [row["candidate_id"] for row in rows if row["passes_internal_walk_forward_gate"]]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "internal_walk_forward",
        "temporal_claim": "internal_non_independent", "source_sha256": source_hashes, "config_sha256": config_hash,
        "discovery_canonical_content_sha256": canonical_sha(discovery), "results": rows, "passing_candidate_ids": passing,
        "decision": "PASS_INTERNAL_WALK_FORWARD_WAITLIST_ONLY" if passing else "REJECT_INTERNAL_WALK_FORWARD",
        "independent_validation": False, "global_holdout_accessed": False, "sqcli_builder_executed": False,
        "performance_promotion_authorized": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True); parser.add_argument("--family", type=Path, required=True); parser.add_argument("--temporal-gate", type=Path, required=True); parser.add_argument("--discovery", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, json.loads(args.family.read_text()), json.loads(args.temporal_gate.read_text()), json.loads(args.discovery.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "passing_candidate_ids": result["passing_candidate_ids"], "results": result["results"], "global_holdout_accessed": False}, indent=2))


if __name__ == "__main__": main()
