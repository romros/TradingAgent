#!/usr/bin/env python3
"""Preregistered cross-sectional BTC/ETH/SOL momentum development screen."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import aggregate, load_m1, metrics


AXES = ("lookback_days", "hold_days", "volatility_lookback_days", "stop_atr")


def daily(path: Path, start: str, end: str, atr_periods=(14, 28)) -> pd.DataFrame:
    frame = aggregate(load_m1(path, start, end), "D1")
    previous = frame.close.shift(1)
    tr = pd.concat([frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()], axis=1).max(axis=1)
    for period in atr_periods: frame[f"atr_{period}"] = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return frame


def parameter_grid(config: dict):
    grid = config["grid"]; keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)): yield dict(zip(keys, values))


def candidate_id(params: dict, prefix: str = "v15") -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return prefix + "-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def leg(frame: pd.DataFrame, entry_idx: int, hold_days: int, side: str, stop_atr: float, atr_period: int,
        costs: dict) -> dict | None:
    direction = 1 if side == "long" else -1; entry = frame.open.iloc[entry_idx]; atr = frame[f"atr_{atr_period}"].iloc[entry_idx - 1]
    if not np.isfinite(entry) or not np.isfinite(atr) or entry <= 0: return None
    stop = entry - direction * stop_atr * atr; exit_idx = min(entry_idx + hold_days - 1, len(frame) - 1)
    if not frame.complete.iloc[entry_idx:exit_idx + 1].all(): return None
    exit_price = None; reason = "time"
    for at in range(entry_idx, exit_idx + 1):
        hit = frame.low.iloc[at] <= stop if direction == 1 else frame.high.iloc[at] >= stop
        if hit:
            exit_idx = at; exit_price = min(frame.open.iloc[at], stop) if direction == 1 else max(frame.open.iloc[at], stop); reason = "stop"; break
    if exit_price is None: exit_price = frame.close.iloc[exit_idx]
    gross = direction * (exit_price / entry - 1); elapsed = max((frame.index[exit_idx] - frame.index[entry_idx]).total_seconds() / 86400, 0) + 1
    result = {"gross": gross, "stop_distance": abs(entry - stop) / entry, "exit_idx": exit_idx, "reason": reason}
    for name, scenario in costs["scenarios"].items():
        bps = costs["opening_fee_bps_per_leg"] + scenario["dynamic_spread_and_impact_bps_per_leg"]
        result[name] = gross - bps / 10_000 - scenario["annual_rollover_pct_per_leg"] / 100 * elapsed / 365.25
    return result


def simulate(frames: dict[str, pd.DataFrame], params: dict, costs: dict, small_account: dict,
             start: str | None = None, end: str | None = None):
    common = sorted(set.intersection(*(set(frame.index) for frame in frames.values())))
    if not common: return []
    reference = frames[next(iter(frames))]; index_lookup = {asset: {stamp: at for at, stamp in enumerate(frame.index)} for asset, frame in frames.items()}
    allowed_start = pd.Timestamp(start, tz="UTC") if start else None
    allowed_end = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    last_exit_date = None; trades = []
    for stamp in common:
        if stamp.weekday() != 0 or (allowed_start is not None and stamp < allowed_start) or (allowed_end is not None and stamp > allowed_end): continue
        if last_exit_date is not None and stamp <= last_exit_date: continue
        returns = {}; valid = True
        for asset, frame in frames.items():
            at = index_lookup[asset][stamp]; lookback = params["lookback_days"]
            if at <= lookback or not frame.complete.iloc[at - lookback:at].all(): valid = False; break
            returns[asset] = frame.close.iloc[at - 1] / frame.close.iloc[at - 1 - lookback] - 1
        if not valid: continue
        ordered = sorted(returns, key=lambda asset: (returns[asset], asset)); chosen = [(ordered[-1], "long")]
        if params["mode"] == "long_strongest_if_positive" and returns[ordered[-1]] <= 0:
            continue
        if params["mode"] == "long_strongest_short_weakest": chosen.append((ordered[0], "short"))
        legs = []
        for asset, side in chosen:
            frame = frames[asset]; at = index_lookup[asset][stamp]
            result = leg(frame, at, params["hold_days"], side, params["stop_atr"], params["volatility_lookback_days"], costs)
            if result is None: valid = False; break
            result.update({"asset": asset, "side": side}); legs.append(result)
        if not valid: continue
        inverse_risk = np.asarray([1 / item["stop_distance"] for item in legs]); weights = inverse_risk / inverse_risk.sum()
        risk_share = small_account["total_risk_per_portfolio_trade_pct"] / 100 / len(legs)
        fixed_oracle_return = costs["oracle_fee_usdc_per_leg"] * len(legs) / small_account["capital_usdc"]
        exit_date = max(frames[item["asset"]].index[item["exit_idx"]] for item in legs)
        trade = {"entry": stamp.isoformat(), "exit": exit_date.isoformat(), "assets": [item["asset"] for item in legs],
                 "sides": [item["side"] for item in legs], "weights": weights.tolist(),
                 "stop_distance": float(sum(weight * item["stop_distance"] for weight, item in zip(weights, legs)))}
        trade["gross"] = float(sum(risk_share * item["gross"] / item["stop_distance"] for item in legs))
        for name in costs["scenarios"]:
            trade[name] = float(sum(risk_share * item[name] / item["stop_distance"] for item in legs) - fixed_oracle_return)
        trade["oracle_cost_usdc"] = costs["oracle_fee_usdc_per_leg"] * len(legs)
        trade["effective_notional_to_capital"] = float(sum(risk_share / item["stop_distance"] for item in legs))
        trades.append(trade); last_exit_date = exit_date
    return trades


def stable_selection(config: dict, rows: list[dict]):
    passing = {row["candidate_id"]: row for row in rows if row["passes_point_gate"]}; grid = config["grid"]
    lookup = {(row["parameters"]["mode"], *(row["parameters"][axis] for axis in AXES)): row["candidate_id"] for row in rows}
    neighbours = {candidate: set() for candidate in passing}
    for candidate, row in passing.items():
        params = row["parameters"]
        for axis in AXES:
            options = grid[axis]; at = options.index(params[axis])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(options):
                    altered = dict(params); altered[axis] = options[other_at]
                    other = lookup.get((altered["mode"], *(altered[key] for key in AXES)))
                    if other in passing: neighbours[candidate].add(other)
        row["passing_orthogonal_neighbours"] = len(neighbours[candidate])
    stable = {candidate for candidate, adjacent in neighbours.items() if len(adjacent) >= config["stability"]["minimum_passing_neighbours"]}; selected = []
    for mode in grid["mode"]:
        nodes = {candidate for candidate, row in passing.items() if row["parameters"]["mode"] == mode}; components = []
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


def run(sources: dict[str, Path], config: dict):
    start, end = config["periods"]["development_from"], config["periods"]["development_to"]
    atr_periods = tuple(config["grid"]["volatility_lookback_days"])
    frames = {asset: daily(path, start, end, atr_periods) for asset, path in sources.items()}; gate = config["pre_registered_development_gate"]; rows = []
    for params in parameter_grid(config):
        trades = simulate(frames, params, config["cost_model"], config["small_account"]); measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        passed = stress["trades"] >= gate["minimum_portfolio_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
        prefix = "v" + config["family_id"].rsplit("_v", 1)[-1]
        rows.append({"candidate_id": candidate_id(params, prefix), "parameters": params, "metrics": measured, "passes_point_gate": bool(passed)})
    stable, selected = stable_selection(config, rows); config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": 1, "family_id": config["family_id"], "period": "development",
            "source_sha256": {asset: file_sha256(path) for asset, path in sources.items()}, "config_sha256": config_hash,
            "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]], "stable_candidate_ids": stable,
            "topology_selected_representatives": selected,
            "diagnostic_top_20": sorted(rows, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:20],
            "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False, "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, json.loads(args.family.read_text())); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives", "validation_accessed")}, indent=2))


if __name__ == "__main__": main()
