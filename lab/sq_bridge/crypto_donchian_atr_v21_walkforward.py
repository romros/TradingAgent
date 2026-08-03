#!/usr/bin/env python3
"""Frozen internal walk-forward for v21 discovery representatives."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.btc_multimechanism_v11 import metrics
from lab.sq_bridge.crypto_donchian_atr_v21 import ASSETS, entry_signal, h4_frame, simulate
from lab.sq_bridge.crypto_universal_reclaim_v20 import schedule_portfolio


def portfolio_trades(frames, params, config, start: str, end: str, signal_cache: dict) -> tuple[list[dict], int]:
    by_asset = {}
    signal_key = tuple(sorted((key, value) for key, value in params.items()
                              if key not in ("stop_atr", "trail_atr", "hold_bars")))
    for asset in ASSETS:
        key = (asset, signal_key)
        if key not in signal_cache:
            signal_cache[key] = entry_signal(frames[asset], params)
        by_asset[asset] = simulate(frames[asset], {**params, "asset": asset},
                                   config["cost_model"], config["small_account"],
                                   signal_start=start, signal_end=end, prepared=signal_cache[key])
    accepted, skipped = schedule_portfolio(by_asset, config["small_account"]["maximum_concurrent_positions"])
    return accepted, len(skipped)


def gate_candidate(trades: list[dict], fold_rows: list[dict], discovery_expectancy_bps: float,
                   config: dict) -> tuple[dict, bool]:
    gate = config["pre_registered_internal_walk_forward_gate"]
    stress = metrics(trades, "stress")
    per_asset = {asset: metrics([trade for trade in trades if trade["asset"] == asset], "stress") for asset in ASSETS}
    drop_one = {asset: metrics([trade for trade in trades if trade["asset"] != asset], "stress") for asset in ASSETS}
    positive_fold_ratio = sum(row["stress"]["net_return_pct"] > 0 for row in fold_rows) / len(fold_rows)
    positive_asset_ratio = sum(value["net_return_pct"] > 0 for value in per_asset.values()) / len(per_asset)
    decay = ((discovery_expectancy_bps - stress["expectancy_bps"]) / discovery_expectancy_bps * 100
             if discovery_expectancy_bps > 0 else 999.0)
    liquidations = sum(trade["liquidation"] for trade in trades)
    passed = (stress["trades"] >= gate["minimum_total_trades"]
              and all(value["trades"] >= gate["minimum_trades_per_asset"] for value in per_asset.values())
              and all(row["stress"]["trades"] >= gate["minimum_trades_per_fold"] for row in fold_rows)
              and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
              and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
              and positive_fold_ratio >= gate["minimum_positive_fold_ratio"]
              and positive_asset_ratio >= gate["minimum_positive_asset_ratio"]
              and all(value["profit_factor"] >= gate["minimum_drop_one_asset_profit_factor"] for value in drop_one.values())
              and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
              and liquidations <= gate["maximum_liquidations"]
              and decay <= gate["maximum_discovery_walk_forward_expectancy_decay_pct"])
    audit = {"aggregate_stress": stress, "per_asset_stress": per_asset,
             "drop_one_asset_stress": drop_one, "positive_fold_ratio": positive_fold_ratio,
             "positive_asset_ratio": positive_asset_ratio, "expectancy_decay_pct": decay,
             "liquidations": liquidations}
    return audit, bool(passed)


def run(sources: dict[str, Path], config: dict, temporal_gate: dict, discovery: dict) -> dict:
    if temporal_gate["decision"] != "PASS_INTERNAL_NON_INDEPENDENT" or temporal_gate["performance_promotion_authorized"]:
        raise ValueError("TEMPORAL_GATE_NOT_INTERNAL_SAFE")
    if discovery["decision"] != "PASS_DISCOVERY_TO_INTERNAL_WF":
        raise ValueError("DISCOVERY_DID_NOT_AUTHORIZE_WALK_FORWARD")
    final_end = config["periods"]["internal_folds"][-1]["to"]
    frames = {asset: h4_frame(path, config["periods"]["discovery_from"], final_end) for asset, path in sources.items()}
    discovery_rows = {row["candidate_id"]: row for row in discovery["passing_candidates"]}
    candidates = []
    for representative in discovery["topology_selected_representatives"]:
        params, cache, all_trades, folds = representative["parameters"], {}, [], []
        for fold in config["periods"]["internal_folds"]:
            trades, skips = portfolio_trades(frames, params, config, fold["from"], fold["to"], cache)
            all_trades.extend(trades)
            folds.append({"id": fold["id"], "from": fold["from"], "to": fold["to"],
                          "stress": metrics(trades, "stress"), "scheduler_skips": skips})
        discovery_expectancy = discovery_rows[representative["candidate_id"]]["metrics"]["stress"]["expectancy_bps"]
        audit, passed = gate_candidate(all_trades, folds, discovery_expectancy, config)
        candidates.append({"candidate_id": representative["candidate_id"], "parameters": params,
                           "discovery_component_size": representative["component_size"],
                           "discovery_stress_expectancy_bps": discovery_expectancy,
                           "folds": folds, **audit, "passes_internal_walk_forward_gate": passed})
    survivors = [row["candidate_id"] for row in candidates if row["passes_internal_walk_forward_gate"]]
    decision = "PASS_INTERNAL_WF_TO_SQ_REPRODUCTION_WAITLIST" if survivors else "REJECT_CRYPTO_DONCHIAN_ATR_INTERNAL_WF"
    return {"schema_version": 1, "family_id": config["family_id"], "period": "internal_walk_forward",
            "temporal_claim": "internal_non_independent", "config_sha256": hashlib.sha256(
                json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "discovery_sha256": hashlib.sha256(json.dumps(discovery, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "candidates": candidates, "survivor_candidate_ids": survivors, "decision": decision,
            "global_holdout_accessed": False, "sqcli_builder_executed": False,
            "performance_promotion_authorized": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True)
    parser.add_argument("--sol", type=Path, required=True); parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--temporal-gate", type=Path, required=True); parser.add_argument("--discovery", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol},
                 json.loads(args.family.read_text()), json.loads(args.temporal_gate.read_text()),
                 json.loads(args.discovery.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"family_id": result["family_id"], "decision": result["decision"],
                      "survivor_candidate_ids": result["survivor_candidate_ids"],
                      "candidates": result["candidates"]}, indent=2))


if __name__ == "__main__":
    main()
