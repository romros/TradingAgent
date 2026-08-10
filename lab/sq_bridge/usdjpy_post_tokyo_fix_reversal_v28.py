#!/usr/bin/env python3
"""Train-only falsification screen for unconditional post-Tokyo-fix reversal v28."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.gbpusd_m15_v1 import load_m15
from lab.sq_bridge.usdjpy_gotobi_tokyo_fix_v27 import daily_windows, metrics, stable_neighbors


def simulate_short(windows: pd.DataFrame, stop_fraction: float) -> pd.DataFrame:
    rows = []
    for row in windows.itertuples():
        stop = row.entry * (1 + stop_fraction)
        stopped = row.high >= stop
        exit_price = stop if stopped else row.exit
        rows.append({"date": row.entry_time, "gross_return": (row.entry - exit_price) / row.entry,
                     "adverse_fraction": max(0, (row.high - row.entry) / row.entry),
                     "stop_fraction": stop_fraction})
    return pd.DataFrame(rows)


def run(source: Path, config: dict) -> dict:
    start, end = config["splits"]["train"]
    axes = [config["search"]["exit_jst_hour"], config["search"]["stop_fraction"]]
    configured_attempts = config["search"]["attempt_budget"]
    actual_attempts = len(list(itertools.product(*axes)))
    if actual_attempts != configured_attempts:
        raise ValueError(
            f"attempt contract mismatch: configured={configured_attempts}, grid={actual_attempts}"
        )
    if any(config.get(flag) is not False for flag in
           ("validation_accessed", "oos_accessed", "holdout_evaluated")):
        raise ValueError("train-only screen requires validation, OOS and holdout to remain sealed")
    frame = load_m15(source).loc[start:end]
    economics, gate = config["economics"], config["train_gate"]
    evaluated = []
    for point in itertools.product(*axes):
        exit_hour, stop = point
        windows = daily_windows(frame, config["search"]["entry_jst_hour"], exit_hour)
        trades = simulate_short(windows, stop)
        scenarios = {name: metrics(trades, bps, economics["oracle_net_cost_usdc"][name], economics)
                     for name, bps in economics["roundtrip_bps"].items()}
        gross_bps = float(trades.gross_return.mean() * 10_000) if not trades.empty else -999
        base, stress = scenarios["base"], scenarios["stress"]
        passed = (base["trades"] >= gate["minimum_trades"]
                  and base["profit_factor"] >= gate["minimum_base_profit_factor"]
                  and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
                  and stress["expectancy_usdc"] >= gate["minimum_stress_expectancy_usdc"]
                  and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
                  and stress["max_drawdown_pct"] <= gate["maximum_drawdown_pct"]
                  and stress["liquidation_count"] == 0
                  and gross_bps >= gate["minimum_gross_return_bps"])
        evaluated.append({"parameters": {"exit_jst_hour": exit_hour, "stop_fraction": stop},
                          "parameter_tuple": list(point), "gross_return_bps": gross_bps,
                          "scenarios": scenarios, "passes_numeric_gate": passed})
    numeric = {tuple(row["parameter_tuple"]) for row in evaluated if row["passes_numeric_gate"]}
    for row in evaluated:
        row["stable_neighbors"] = stable_neighbors(tuple(row["parameter_tuple"]), numeric, axes)
        row["passes_train_gate"] = (row["passes_numeric_gate"]
                                     and row["stable_neighbors"] >= gate["minimum_stable_neighbors"])
    survivors = [row for row in evaluated if row["passes_train_gate"]]
    return {"schema_version": 1, "campaign_id": config["campaign_id"], "stage": "pre_sq_falsification",
            "decision": "PASS_TO_SQ" if survivors else "REJECT_NO_SQ", "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "train_window": [start, end],
            "bars_loaded": int(len(frame)), "attempted": len(evaluated), "survivor_count": len(survivors),
            "survivors": survivors, "all_results": evaluated, "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    raw = args.config.read_bytes(); config = json.loads(raw); result = run(Path(config["source"]), config)
    result["config_sha256"] = hashlib.sha256(raw).hexdigest(); args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("decision", "attempted", "survivor_count",
                                                    "validation_accessed", "holdout_accessed")}, indent=2))


if __name__ == "__main__":
    main()
