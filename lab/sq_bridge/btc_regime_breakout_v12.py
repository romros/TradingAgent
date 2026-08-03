#!/usr/bin/env python3
"""Development-only BTC D1-regime Donchian screen."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import aggregate, enrich, grids, load_m1, metrics, simulate, stable_regions


def regime_frames(raw, timeframes):
    daily = enrich(aggregate(raw, "D1"))
    regimes = {}
    for period in (100, 200):
        regimes[period] = (daily.close.shift(1) - daily[f"ema_{period}"].shift(1))
    frames = {}
    for timeframe in timeframes:
        frame = enrich(aggregate(raw, timeframe))
        for period, regime in regimes.items():
            frame[f"regime_{period}"] = regime.reindex(frame.index, method="ffill")
        frames[timeframe] = frame
    return frames


def run(source: Path, config: dict) -> dict:
    start, end = config["periods"]["development_from"], config["periods"]["development_to"]
    raw = load_m1(source, start, end); frames = regime_frames(raw, ("H1", "H4"))
    gate = config["pre_registered_development_gate"]; rows = []
    for mechanism, params in grids(config):
        trades = simulate(frames[params["timeframe"]], mechanism, params, config["cost_model"])
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        passed = stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
        raw_identity = json.dumps({"family": config["family_id"], "mechanism": mechanism, **params}, sort_keys=True, separators=(",", ":"))
        identity = "v12-" + hashlib.sha256(raw_identity.encode()).hexdigest()[:12]
        rows.append({"candidate_id": identity, "mechanism": mechanism, "parameters": params,
                     "metrics": measured, "passes_point_gate": bool(passed)})
    adapted = dict(config); adapted["pre_registered_train_gate"] = config["pre_registered_development_gate"]
    stable, selected = stable_regions(adapted, rows)
    eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= gate["minimum_trades"]]
    diagnostics = sorted(eligible, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:20]
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": 1, "family_id": config["family_id"], "period": "development",
            "source_sha256": file_sha256(source), "config_sha256": config_hash,
            "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]],
            "stable_candidate_ids": stable, "topology_selected_representatives": selected,
            "diagnostic_top_20": diagnostics, "validation_accessed": False, "oos_accessed": False,
            "holdout_accessed": False, "sqcli_executed": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = run(args.source, json.loads(args.family.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives", "validation_accessed")}, indent=2))


if __name__ == "__main__": main()
