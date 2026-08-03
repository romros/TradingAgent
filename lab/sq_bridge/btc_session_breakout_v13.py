#!/usr/bin/env python3
"""Preregistered development screen for fixed-UTC BTC session breakouts."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256
from lab.sq_bridge.btc_multimechanism_v11 import aggregate, enrich, load_m1, metrics


AXES = ("range_hours", "trade_window_hours", "stop_atr", "hold_bars")
GROUP = ("session_start_utc", "day_group", "mode", "side")


def parameter_grid(config: dict):
    grid = config["grid"]
    keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def identity(params: dict, prefix: str) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return prefix + "-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def session_signal(frame: pd.DataFrame, params: dict) -> pd.Series:
    signal = pd.Series(False, index=frame.index)
    start_hour = params["session_start_utc"]
    first_day = frame.index.min().normalize(); last_day = frame.index.max().normalize()
    for day in pd.date_range(first_day, last_day, freq="D", tz="UTC"):
        weekday = day.weekday() < 5
        if (params["day_group"] == "weekday") != weekday:
            continue
        anchor = day + pd.Timedelta(hours=start_hour)
        range_end = anchor + pd.Timedelta(hours=params["range_hours"])
        window_end = range_end + pd.Timedelta(hours=params["trade_window_hours"])
        range_bars = frame.loc[(frame.index >= anchor) & (frame.index < range_end)]
        eligible = frame.loc[(frame.index >= range_end) & (frame.index < window_end)]
        if len(range_bars) != params["range_hours"] or not range_bars.complete.all() or len(eligible) < 2:
            continue
        trigger_long = (params["side"] == "long") == (params.get("mode", "breakout") == "breakout")
        boundary = range_bars.high.max() if trigger_long else range_bars.low.min()
        crossed = eligible.close > boundary if trigger_long else eligible.close < boundary
        crossed &= eligible.complete
        hits = eligible.index[crossed]
        if len(hits) and hits[0] + pd.Timedelta(hours=1) < window_end:
            signal.loc[hits[0]] = True
    return signal


def add_signal(frame: pd.DataFrame, params: dict) -> pd.DataFrame:
    out = frame.copy(); out["session_signal"] = session_signal(out, params); return out


def simulate_candidate(frame: pd.DataFrame, params: dict, costs: dict, start: str | None = None, end: str | None = None,
                       precomputed_signal: pd.Series | None = None):
    prepared = frame.copy(); prepared["session_signal"] = precomputed_signal if precomputed_signal is not None else session_signal(prepared, params)
    # Reuse the tested next-open/ATR-stop/time-exit engine through a dedicated
    # signal column recognized locally, without changing other mechanisms.
    prepared["_signal"] = prepared.session_signal
    direction = 1 if params["side"] == "long" else -1
    opened, high, low, close, atr = (prepared[name].to_numpy() for name in ("open", "high", "low", "close", "atr"))
    complete = prepared.complete.to_numpy(); entries = prepared._signal.to_numpy(); dates = prepared.index
    allowed_start = pd.Timestamp(start, tz="UTC") if start else None
    allowed_end = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if end else None
    last_exit = -1; trades = []
    for signal_idx in np.flatnonzero(entries):
        if allowed_start is not None and dates[signal_idx] < allowed_start: continue
        if allowed_end is not None and dates[signal_idx] > allowed_end: continue
        entry_idx = signal_idx + 1
        if entry_idx >= len(prepared) or entry_idx <= last_exit or (allowed_end is not None and dates[entry_idx] > allowed_end) or not complete[entry_idx] or not np.isfinite(atr[signal_idx]):
            continue
        entry = opened[entry_idx]; stop = entry - direction * params["stop_atr"] * atr[signal_idx]
        exit_idx = min(entry_idx + params["hold_bars"] - 1, len(prepared) - 1); exit_price = None; invalid = False; reason = "time"
        for bar_idx in range(entry_idx, exit_idx + 1):
            if not complete[bar_idx]: invalid = True; exit_idx = bar_idx; break
            hit = low[bar_idx] <= stop if direction == 1 else high[bar_idx] >= stop
            if hit:
                exit_idx = bar_idx; exit_price = min(opened[bar_idx], stop) if direction == 1 else max(opened[bar_idx], stop); reason = "stop"; break
        if invalid: last_exit = exit_idx; continue
        if exit_price is None: exit_price = close[exit_idx]
        gross = direction * (exit_price / entry - 1); days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0)
        trade = {"entry": dates[entry_idx].isoformat(), "exit": dates[exit_idx].isoformat(), "gross": gross,
                 "stop_distance": abs(entry - stop) / entry, "reason": reason}
        for name, scenario in costs["scenarios"].items():
            bps = costs["ostium_opening_fee_bps"] + scenario["dynamic_spread_and_impact_bps"]
            trade[name] = gross - bps / 10_000 - scenario["annual_rollover_pct"] / 100 * days / 365.25
        trades.append(trade); last_exit = exit_idx
    return trades


def stable_selection(config: dict, rows: list[dict]):
    passing = {row["candidate_id"]: row for row in rows if row["passes_point_gate"]}
    lookup = {tuple(row["parameters"][key] for key in (*GROUP, *AXES)): row["candidate_id"] for row in rows}
    neighbours = {candidate: set() for candidate in passing}; grid = config["grid"]
    for candidate, row in passing.items():
        params = row["parameters"]
        for axis in AXES:
            options = grid[axis]; at = options.index(params[axis])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(options):
                    altered = dict(params); altered[axis] = options[other_at]
                    other = lookup.get(tuple(altered[key] for key in (*GROUP, *AXES)))
                    if other in passing: neighbours[candidate].add(other)
        row["passing_orthogonal_neighbours"] = len(neighbours[candidate])
    stable = {candidate for candidate, adjacent in neighbours.items() if len(adjacent) >= config["stability"]["minimum_passing_neighbours"]}
    selected = []
    for values in itertools.product(*(grid[key] for key in GROUP)):
        nodes = {candidate for candidate, row in passing.items() if tuple(row["parameters"][key] for key in GROUP) == values}
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
            return sum(abs(grid[key].index(a[key]) - grid[key].index(b[key])) for key in AXES)
        medoid = min(component, key=lambda item: (sum(distance(item, other) for other in component), item))
        selected.append({"candidate_id": medoid, "component_size": len(component), "parameters": passing[medoid]["parameters"],
                         "performance_metrics_used": False})
    return sorted(stable), selected


def run(source: Path, config: dict):
    start, end = config["periods"]["development_from"], config["periods"]["development_to"]
    frame = enrich(aggregate(load_m1(source, start, end), "H1")); gate = config["pre_registered_development_gate"]; rows = []
    signal_cache = {}
    for params in parameter_grid(config):
        signal_key = tuple(params[key] for key in ("session_start_utc", "day_group", "mode", "range_hours", "trade_window_hours", "side"))
        if signal_key not in signal_cache: signal_cache[signal_key] = session_signal(frame, params)
        trades = simulate_candidate(frame, params, config["cost_model"], precomputed_signal=signal_cache[signal_key]); measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}; stress = measured["stress"]
        passed = stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
        prefix = config["family_id"].rsplit("_v", 1)[-1]
        rows.append({"candidate_id": identity(params, "v" + prefix), "parameters": params, "metrics": measured, "passes_point_gate": bool(passed)})
    stable, selected = stable_selection(config, rows)
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= gate["minimum_trades"]]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "development", "source_sha256": file_sha256(source),
            "config_sha256": config_hash, "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]], "stable_candidate_ids": stable,
            "topology_selected_representatives": selected,
            "diagnostic_top_20": sorted(eligible, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:20],
            "validation_accessed": False, "oos_accessed": False, "holdout_accessed": False, "sqcli_executed": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, required=True); parser.add_argument("--family", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = run(args.source, json.loads(args.family.read_text())); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives", "validation_accessed")}, indent=2))


if __name__ == "__main__": main()
