#!/usr/bin/env python3
"""Preregistered v19 crypto H1 capitulation/reclaim discovery screen."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import metrics
from lab.sq_bridge.crypto_intraday_compression_v18 import hourly, leverage_plan, trade_diagnostics


AXES = ("shock_return", "range_atr", "reclaim_hours", "reclaim_fraction", "stop_atr", "hold_bars")
GROUP = ("asset", "side", "session_start_utc", "day_group")
SIGNAL_KEYS = ("side", "session_start_utc", "day_group", "shock_return", "range_atr", "reclaim_hours", "reclaim_fraction")


def parameter_grid(config: dict):
    grid = config["grid"]; keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)): yield dict(zip(keys, values))


def candidate_id(params: dict) -> str:
    return "v19-" + hashlib.sha256(json.dumps(params, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:12]


def reclaim_signals(frame: pd.DataFrame, params: dict) -> tuple[np.ndarray, np.ndarray]:
    count = len(frame); signals = np.zeros(count, dtype=bool); shock_atr = np.full(count, np.nan)
    close, high, low, complete, atr = (frame[name].to_numpy() for name in ("close", "high", "low", "complete", "atr"))
    prior_close = np.r_[np.nan, close[:-1]]; returns = close / prior_close - 1
    prior_atr = np.r_[np.nan, atr[:-1]]; true_range = np.maximum(high - low, np.maximum(abs(high - prior_close), abs(low - prior_close)))
    direction = 1 if params["side"] == "long" else -1
    shock = returns <= -params["shock_return"] if direction == 1 else returns >= params["shock_return"]
    shock &= true_range >= params["range_atr"] * prior_atr
    shock &= complete & np.isfinite(prior_atr) & np.isfinite(atr)
    shock &= ((frame.index.hour // 8) * 8 == params["session_start_utc"])
    weekday = frame.index.dayofweek < 5; shock &= weekday if params["day_group"] == "weekday" else ~weekday
    for at in np.flatnonzero(shock):
        level = low[at] + params["reclaim_fraction"] * (high[at] - low[at]) if direction == 1 else high[at] - params["reclaim_fraction"] * (high[at] - low[at])
        end = min(at + params["reclaim_hours"], count - 1)
        for trigger in range(at + 1, end + 1):
            if not complete[trigger]: break
            reclaimed = close[trigger] >= level if direction == 1 else close[trigger] <= level
            if reclaimed:
                if not signals[trigger]: signals[trigger], shock_atr[trigger] = True, atr[at]
                break
    return signals, shock_atr


def simulate(frame: pd.DataFrame, params: dict, costs: dict, account: dict,
             signal_start: str | None = None, signal_end: str | None = None,
             prepared: tuple[np.ndarray, np.ndarray] | None = None) -> list[dict]:
    signals, signal_atr = prepared if prepared is not None else reclaim_signals(frame, params)
    direction = 1 if params["side"] == "long" else -1
    opened, high, low, close = (frame[name].to_numpy() for name in ("open", "high", "low", "close"))
    complete, dates = frame.complete.to_numpy(), frame.index
    allowed_start = pd.Timestamp(signal_start, tz="UTC") if signal_start else None
    allowed_end = pd.Timestamp(signal_end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if signal_end else None
    last_exit = -1; trades = []
    for signal_idx in np.flatnonzero(signals):
        if allowed_start is not None and dates[signal_idx] < allowed_start: continue
        if allowed_end is not None and dates[signal_idx] > allowed_end: continue
        entry_idx = signal_idx + 1
        if (entry_idx >= len(frame) or entry_idx <= last_exit or not complete[entry_idx]
                or (allowed_end is not None and dates[entry_idx] > allowed_end) or not np.isfinite(signal_atr[signal_idx])): continue
        entry = opened[entry_idx]; stop_distance = params["stop_atr"] * signal_atr[signal_idx] / entry
        plan = leverage_plan(stop_distance, params["asset"], account)
        if plan is None: continue
        stop = entry * (1 - direction * stop_distance); liquidation_price = entry * (1 - direction * plan["liquidation_distance"])
        planned_exit = entry_idx + params["hold_bars"] - 1
        if planned_exit >= len(frame) or (allowed_end is not None and dates[planned_exit] > allowed_end): continue
        exit_idx = planned_exit; exit_price = None
        reason, liquidation, invalid = "time", False, False
        for at in range(entry_idx, exit_idx + 1):
            if not complete[at]: invalid = True; exit_idx = at; break
            adverse_open = direction * (opened[at] / entry - 1)
            if at > entry_idx and adverse_open <= -plan["liquidation_distance"]:
                exit_idx, exit_price, reason, liquidation = at, liquidation_price, "liquidation_gap", True; break
            stop_hit = low[at] <= stop if direction == 1 else high[at] >= stop
            if stop_hit:
                exit_idx, exit_price, reason = at, (min(opened[at], stop) if direction == 1 else max(opened[at], stop)), "stop"; break
        if invalid: last_exit = exit_idx; continue
        if exit_price is None: exit_price = close[exit_idx]
        gross = direction * (exit_price / entry - 1); elapsed_days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0)
        trade = {"entry": dates[entry_idx].isoformat(), "exit": dates[exit_idx].isoformat(), "gross_underlying": gross,
            "stop_distance": stop_distance, "leverage": plan["leverage"], "exposure_to_capital": plan["exposure"],
            "margin_fraction": plan["margin_fraction"], "liquidation": liquidation, "reason": reason}
        for name, scenario in costs["scenarios"].items():
            if liquidation: account_return = -plan["margin_fraction"]
            else:
                net = gross - (costs["opening_fee_bps_per_trade"] + scenario["dynamic_spread_and_impact_bps"]) / 10_000 - scenario["annual_rollover_pct"] / 100 * elapsed_days / 365.25
                account_return = plan["exposure"] * net
            trade[name] = account_return - costs["oracle_fee_usdc_per_trade"] / account["capital_usdc"]
        trades.append(trade); last_exit = exit_idx
    return trades


def stable_selection(config: dict, rows: list[dict]):
    passing = {row["candidate_id"]: row for row in rows if row["passes_point_gate"]}; grid = config["grid"]
    lookup = {tuple(row["parameters"][key] for key in (*GROUP, *AXES)): row["candidate_id"] for row in rows}
    neighbours = {candidate: set() for candidate in passing}
    for candidate, row in passing.items():
        params = row["parameters"]
        for axis in AXES:
            values = grid[axis]; at = values.index(params[axis])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(values):
                    altered = dict(params); altered[axis] = values[other_at]
                    other = lookup.get(tuple(altered[key] for key in (*GROUP, *AXES)))
                    if other in passing: neighbours[candidate].add(other)
        row["passing_orthogonal_neighbours"] = len(neighbours[candidate])
    stable = {candidate for candidate, adjacent in neighbours.items() if len(adjacent) >= config["stability"]["minimum_passing_neighbours"]}; selected = []
    for group in itertools.product(*(grid[key] for key in GROUP)):
        nodes = {candidate for candidate, row in passing.items() if tuple(row["parameters"][key] for key in GROUP) == group}; components = []
        while nodes:
            frontier = {min(nodes)}; component = set()
            while frontier:
                node = frontier.pop(); component.add(node); nodes.remove(node); frontier |= neighbours[node] & nodes
            if component & stable: components.append(component)
        if not components: continue
        component = sorted(components, key=lambda item: (-len(item), sorted(item)))[0]
        def distance(left, right):
            a, b = passing[left]["parameters"], passing[right]["parameters"]
            return sum(abs(grid[axis].index(a[axis]) - grid[axis].index(b[axis])) for axis in AXES)
        medoid = min(component, key=lambda item: (sum(distance(item, other) for other in component), item))
        selected.append({"candidate_id": medoid, "component_size": len(component), "parameters": passing[medoid]["parameters"], "performance_metrics_used": False})
    return sorted(stable), selected


def run(sources: dict[str, Path], config: dict, temporal_gate: dict) -> dict:
    if temporal_gate["decision"] != "PASS_INTERNAL_NON_INDEPENDENT" or temporal_gate["performance_promotion_authorized"]:
        raise ValueError("TEMPORAL_GATE_NOT_INTERNAL_SAFE")
    start, end = config["periods"]["discovery_from"], config["periods"]["discovery_to"]
    frames = {asset: hourly(path, start, end) for asset, path in sources.items()}; gate = config["pre_registered_discovery_gate"]
    signal_cache, rows = {}, []
    for params in parameter_grid(config):
        key = (params["asset"], *(params[name] for name in SIGNAL_KEYS))
        if key not in signal_cache: signal_cache[key] = reclaim_signals(frames[params["asset"]], params)
        trades = simulate(frames[params["asset"]], params, config["cost_model"], config["small_account"], prepared=signal_cache[key])
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        liquidations = sum(trade["liquidation"] for trade in trades); expectancy_usdc = stress["expectancy_bps"] / 10_000 * config["small_account"]["capital_usdc"]
        passed = (stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
            and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"] and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
            and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"] and liquidations <= gate["maximum_liquidations"]
            and expectancy_usdc >= gate["minimum_net_expectancy_usdc"])
        rows.append({"candidate_id": candidate_id(params), "parameters": params, "metrics": measured, "liquidations": liquidations,
            "stress_expectancy_usdc": expectancy_usdc, "trade_diagnostics": trade_diagnostics(trades), "passes_point_gate": bool(passed)})
    stable, selected = stable_selection(config, rows); eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= gate["minimum_trades"]]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "discovery", "temporal_claim": "internal_non_independent",
        "source_sha256": {asset: file_sha256(path) for asset, path in sources.items()},
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "temporal_gate_sha256": hashlib.sha256(json.dumps(temporal_gate, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
        "passing_candidates": [row for row in rows if row["passes_point_gate"]], "stable_candidate_ids": stable,
        "topology_selected_representatives": selected,
        "diagnostic_top_30": sorted(eligible, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:30],
        "internal_folds_accessed": False, "global_holdout_accessed": False, "sqcli_builder_executed": False,
        "performance_promotion_authorized": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True); parser.add_argument("--family", type=Path, required=True); parser.add_argument("--temporal-gate", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, json.loads(args.family.read_text()), json.loads(args.temporal_gate.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives", "internal_folds_accessed")}, indent=2))


if __name__ == "__main__": main()
