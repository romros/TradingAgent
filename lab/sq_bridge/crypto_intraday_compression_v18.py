#!/usr/bin/env python3
"""Preregistered v18 crypto intraday compression development screen."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import aggregate, load_m1, metrics


AXES = ("compression_lookback_hours", "compression_quantile", "channel_hours", "stop_atr", "hold_bars")
GROUP = ("asset", "mode", "side", "session_start_utc", "day_group")


def parameter_grid(config: dict):
    grid = config["grid"]
    keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def candidate_id(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return "v18-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def hourly(path: Path, start: str, end: str) -> pd.DataFrame:
    frame = aggregate(load_m1(path, start, end), "H1")
    previous = frame.close.shift(1)
    tr = pd.concat((frame.high - frame.low, (frame.high - previous).abs(), (frame.low - previous).abs()), axis=1).max(axis=1)
    frame["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    frame["normalized_atr"] = frame.atr / frame.close
    return frame


def entry_signal(frame: pd.DataFrame, params: dict) -> pd.Series:
    lookback, channel = params["compression_lookback_hours"], params["channel_hours"]
    complete = frame.complete.rolling(max(lookback + 1, channel + 1)).min().fillna(False).astype(bool)
    prior_volatility = frame.normalized_atr.shift(1)
    rank = prior_volatility.rolling(lookback).rank(pct=True)
    compressed = rank <= params["compression_quantile"]
    prior_high = frame.high.shift(1).rolling(channel).max()
    prior_low = frame.low.shift(1).rolling(channel).min()
    upward_trigger = (params["mode"] == "breakout") == (params["side"] == "long")
    price_trigger = frame.close > prior_high if upward_trigger else frame.close < prior_low
    session = (frame.index.hour // 8) * 8 == params["session_start_utc"]
    weekday = frame.index.dayofweek < 5
    day = weekday if params["day_group"] == "weekday" else ~weekday
    return compressed & price_trigger & complete & session & day


def leverage_plan(stop_distance: float, asset: str, account: dict) -> dict | None:
    if not np.isfinite(stop_distance) or stop_distance <= 0:
        return None
    maximum_safe = math.floor(1 / (stop_distance * account["liquidation_buffer_over_stop"]))
    leverage = min(maximum_safe, account["venue_max_leverage"][asset])
    if leverage < 1:
        return None
    risk_fraction = account["risk_per_trade_pct"] / 100
    exposure = risk_fraction / stop_distance
    margin_fraction = exposure / leverage
    if margin_fraction > account["maximum_margin_pct"] / 100:
        return None
    return {"leverage": leverage, "exposure": exposure, "margin_fraction": margin_fraction,
            "liquidation_distance": 1 / leverage}


def simulate(frame: pd.DataFrame, params: dict, costs: dict, account: dict,
             signal_start: str | None = None, signal_end: str | None = None) -> list[dict]:
    signals = entry_signal(frame, params).fillna(False).to_numpy()
    direction = 1 if params["side"] == "long" else -1
    opened, high, low, close, atr = (frame[name].to_numpy() for name in ("open", "high", "low", "close", "atr"))
    complete, dates = frame.complete.to_numpy(), frame.index
    allowed_start = pd.Timestamp(signal_start, tz="UTC") if signal_start else None
    allowed_end = pd.Timestamp(signal_end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if signal_end else None
    last_exit = -1; trades = []
    for signal_idx in np.flatnonzero(signals):
        if allowed_start is not None and dates[signal_idx] < allowed_start: continue
        if allowed_end is not None and dates[signal_idx] > allowed_end: continue
        entry_idx = signal_idx + 1
        if (entry_idx >= len(frame) or entry_idx <= last_exit or not complete[entry_idx]
                or (allowed_end is not None and dates[entry_idx] > allowed_end) or not np.isfinite(atr[signal_idx])):
            continue
        entry = opened[entry_idx]
        stop_distance = params["stop_atr"] * atr[signal_idx] / entry
        plan = leverage_plan(stop_distance, params["asset"], account)
        if plan is None: continue
        stop = entry * (1 - direction * stop_distance)
        exit_idx = min(entry_idx + params["hold_bars"] - 1, len(frame) - 1)
        exit_price = None; reason = "time"; liquidation = False; invalid = False
        liquidation_price = entry * (1 - direction * plan["liquidation_distance"])
        for at in range(entry_idx, exit_idx + 1):
            if not complete[at]: invalid = True; exit_idx = at; break
            adverse_open = direction * (opened[at] / entry - 1)
            if at > entry_idx and adverse_open <= -plan["liquidation_distance"]:
                exit_idx, exit_price, reason, liquidation = at, liquidation_price, "liquidation_gap", True
                break
            stop_hit = low[at] <= stop if direction == 1 else high[at] >= stop
            if stop_hit:
                exit_idx = at; exit_price = min(opened[at], stop) if direction == 1 else max(opened[at], stop); reason = "stop"; break
        if invalid: last_exit = exit_idx; continue
        if exit_price is None: exit_price = close[exit_idx]
        gross_underlying = direction * (exit_price / entry - 1)
        elapsed_days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0)
        trade = {"entry": dates[entry_idx].isoformat(), "exit": dates[exit_idx].isoformat(),
                 "gross_underlying": gross_underlying, "stop_distance": stop_distance,
                 "leverage": plan["leverage"], "exposure_to_capital": plan["exposure"],
                 "margin_fraction": plan["margin_fraction"], "liquidation": liquidation, "reason": reason}
        for name, scenario in costs["scenarios"].items():
            if liquidation:
                account_return = -plan["margin_fraction"]
            else:
                underlying_net = (gross_underlying - (costs["opening_fee_bps_per_trade"]
                    + scenario["dynamic_spread_and_impact_bps"]) / 10_000
                    - scenario["annual_rollover_pct"] / 100 * elapsed_days / 365.25)
                account_return = plan["exposure"] * underlying_net
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
    stable = {candidate for candidate, adjacent in neighbours.items()
              if len(adjacent) >= config["stability"]["minimum_passing_neighbours"]}
    selected = []
    for group in itertools.product(*(grid[key] for key in GROUP)):
        nodes = {candidate for candidate, row in passing.items()
                 if tuple(row["parameters"][key] for key in GROUP) == group}
        components = []
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
        selected.append({"candidate_id": medoid, "component_size": len(component),
                         "parameters": passing[medoid]["parameters"], "performance_metrics_used": False})
    return sorted(stable), selected


def trade_diagnostics(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0}
    durations = [(pd.Timestamp(trade["exit"]) - pd.Timestamp(trade["entry"])).total_seconds() / 3600 for trade in trades]
    return {"trades": len(trades), "median_duration_hours": float(np.median(durations)),
        "maximum_duration_hours": float(max(durations)), "stop_exit_ratio": sum(trade["reason"] == "stop" for trade in trades) / len(trades),
        "median_leverage": float(np.median([trade["leverage"] for trade in trades])),
        "minimum_leverage": min(trade["leverage"] for trade in trades), "maximum_leverage": max(trade["leverage"] for trade in trades),
        "median_exposure_to_capital": float(np.median([trade["exposure_to_capital"] for trade in trades])),
        "maximum_exposure_to_capital": max(trade["exposure_to_capital"] for trade in trades),
        "median_margin_pct": float(np.median([trade["margin_fraction"] for trade in trades]) * 100),
        "maximum_margin_pct": max(trade["margin_fraction"] for trade in trades) * 100,
        "liquidations": sum(trade["liquidation"] for trade in trades)}


def run(sources: dict[str, Path], config: dict) -> dict:
    start, end = config["periods"]["development_from"], config["periods"]["development_to"]
    frames = {asset: hourly(path, start, end) for asset, path in sources.items()}
    gate, rows = config["pre_registered_development_gate"], []
    for params in parameter_grid(config):
        trades = simulate(frames[params["asset"]], params, config["cost_model"], config["small_account"])
        measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        liquidations = sum(trade["liquidation"] for trade in trades)
        expectancy_usdc = stress["expectancy_bps"] / 10_000 * config["small_account"]["capital_usdc"]
        passed = (stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
            and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
            and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
            and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
            and liquidations <= gate["maximum_liquidations"] and expectancy_usdc >= gate["minimum_net_expectancy_usdc"])
        rows.append({"candidate_id": candidate_id(params), "parameters": params, "metrics": measured,
                     "liquidations": liquidations, "stress_expectancy_usdc": expectancy_usdc,
                     "trade_diagnostics": trade_diagnostics(trades),
                     "passes_point_gate": bool(passed)})
    stable, selected = stable_selection(config, rows)
    eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= gate["minimum_trades"]]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "development",
        "source_sha256": {asset: file_sha256(path) for asset, path in sources.items()},
        "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "coverage": {asset: {"from": frame.index.min().isoformat(), "to": frame.index.max().isoformat(),
            "bars": len(frame), "incomplete_bars": int((~frame.complete).sum())} for asset, frame in frames.items()},
        "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
        "passing_candidates": [row for row in rows if row["passes_point_gate"]], "stable_candidate_ids": stable,
        "topology_selected_representatives": selected,
        "diagnostic_top_30": sorted(eligible, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:30],
        "validation_accessed": False, "holdout_accessed": False, "sqcli_builder_executed": False,
        "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True); parser.add_argument("--sol", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    config = json.loads(args.family.read_text())
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol}, config)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives", "validation_accessed")}, indent=2))


if __name__ == "__main__": main()
