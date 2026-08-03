#!/usr/bin/env python3
"""V21 universal short-horizon H4 Donchian/ATR trend screen."""
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
from lab.sq_bridge.crypto_intraday_compression_v18 import leverage_plan, trade_diagnostics
from lab.sq_bridge.crypto_universal_reclaim_v20 import schedule_portfolio


ASSETS = ("BTCUSD", "ETHUSD", "SOLUSD")
AXES = ("channel_bars", "entry_buffer_atr", "ema_regime_bars", "stop_atr", "trail_atr", "hold_bars")
GROUP = ("side", "session_start_utc", "day_group")
SIGNAL_KEYS = (*GROUP, "channel_bars", "entry_buffer_atr", "ema_regime_bars")


def parameter_grid(config: dict):
    grid = config["grid"]
    keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def candidate_id(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return "v21-" + hashlib.sha256(raw).hexdigest()[:12]


def h4_frame(path: Path, start: str, end: str) -> pd.DataFrame:
    frame = aggregate(load_m1(path, start, end), "H4")
    previous = frame.close.shift(1)
    true_range = pd.concat((frame.high - frame.low, (frame.high - previous).abs(),
                            (frame.low - previous).abs()), axis=1).max(axis=1)
    frame["atr"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return frame


def entry_signal(frame: pd.DataFrame, params: dict) -> np.ndarray:
    channel = params["channel_bars"]
    prior_high = frame.high.shift(1).rolling(channel).max()
    prior_low = frame.low.shift(1).rolling(channel).min()
    required_complete = frame.complete.shift(1).rolling(channel).min().fillna(False).astype(bool)
    buffer = params["entry_buffer_atr"] * frame.atr
    if params["side"] == "long":
        signal = frame.close > prior_high + buffer
    else:
        signal = frame.close < prior_low - buffer
    ema_bars = params["ema_regime_bars"]
    if ema_bars:
        prior_ema = frame.close.ewm(span=ema_bars, adjust=False, min_periods=ema_bars).mean().shift(1)
        regime = frame.close > prior_ema if params["side"] == "long" else frame.close < prior_ema
        signal &= regime
    session = frame.index.hour == params["session_start_utc"]
    weekday = frame.index.dayofweek < 5
    signal &= session
    signal &= weekday if params["day_group"] == "weekday" else ~weekday
    signal &= required_complete & frame.complete & frame.atr.notna()
    return signal.fillna(False).to_numpy()


def simulate(frame: pd.DataFrame, params: dict, costs: dict, account: dict,
             signal_start: str | None = None, signal_end: str | None = None,
             prepared: np.ndarray | None = None) -> list[dict]:
    signals = prepared if prepared is not None else entry_signal(frame, params)
    direction = 1 if params["side"] == "long" else -1
    opened, high, low, close, atr = (frame[name].to_numpy() for name in ("open", "high", "low", "close", "atr"))
    complete, dates = frame.complete.to_numpy(), frame.index
    allowed_start = pd.Timestamp(signal_start, tz="UTC") if signal_start else None
    allowed_end = (pd.Timestamp(signal_end, tz="UTC") + pd.Timedelta(days=1)
                   - pd.Timedelta(microseconds=1)) if signal_end else None
    last_exit, trades = -1, []
    for signal_idx in np.flatnonzero(signals):
        if allowed_start is not None and dates[signal_idx] < allowed_start:
            continue
        if allowed_end is not None and dates[signal_idx] > allowed_end:
            continue
        entry_idx = signal_idx + 1
        planned_exit = entry_idx + params["hold_bars"] - 1
        if (entry_idx >= len(frame) or entry_idx <= last_exit or planned_exit >= len(frame)
                or not complete[entry_idx] or not np.isfinite(atr[signal_idx])
                or (allowed_end is not None and dates[planned_exit] > allowed_end)):
            continue
        entry = opened[entry_idx]
        stop_distance = params["stop_atr"] * atr[signal_idx] / entry
        plan = leverage_plan(stop_distance, params["asset"], account)
        if plan is None:
            continue
        initial_stop = entry * (1 - direction * stop_distance)
        active_stop = initial_stop
        liquidation_price = entry * (1 - direction * plan["liquidation_distance"])
        favorable_extreme = entry
        exit_idx, exit_price, reason, liquidation, invalid = planned_exit, None, "time", False, False
        for at in range(entry_idx, planned_exit + 1):
            if not complete[at]:
                invalid, exit_idx = True, at
                break
            adverse_open = direction * (opened[at] / entry - 1)
            if at > entry_idx and adverse_open <= -plan["liquidation_distance"]:
                exit_idx, exit_price, reason, liquidation = at, liquidation_price, "liquidation_gap", True
                break
            stop_hit = low[at] <= active_stop if direction == 1 else high[at] >= active_stop
            if stop_hit:
                exit_idx = at
                exit_price = min(opened[at], active_stop) if direction == 1 else max(opened[at], active_stop)
                reason = "trailing_stop" if active_stop != initial_stop else "initial_stop"
                break
            # A bar's extreme can only tighten the stop for the next bar.
            if params["trail_atr"] > 0:
                if direction == 1:
                    favorable_extreme = max(favorable_extreme, high[at])
                    active_stop = max(active_stop, favorable_extreme - params["trail_atr"] * atr[at])
                else:
                    favorable_extreme = min(favorable_extreme, low[at])
                    active_stop = min(active_stop, favorable_extreme + params["trail_atr"] * atr[at])
        if invalid:
            last_exit = exit_idx
            continue
        if exit_price is None:
            exit_price = close[exit_idx]
        gross = direction * (exit_price / entry - 1)
        elapsed_days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0)
        trade = {"entry": dates[entry_idx].isoformat(), "exit": dates[exit_idx].isoformat(),
                 "gross_underlying": gross, "stop_distance": stop_distance,
                 "leverage": plan["leverage"], "exposure_to_capital": plan["exposure"],
                 "margin_fraction": plan["margin_fraction"], "liquidation": liquidation,
                 "reason": reason}
        for name, scenario in costs["scenarios"].items():
            if liquidation:
                account_return = -plan["margin_fraction"]
            else:
                net = (gross - (costs["opening_fee_bps_per_trade"]
                       + scenario["dynamic_spread_and_impact_bps"]) / 10_000
                       - scenario["annual_rollover_pct"] / 100 * elapsed_days / 365.25)
                account_return = plan["exposure"] * net
            trade[name] = account_return - costs["oracle_fee_usdc_per_trade"] / account["capital_usdc"]
        trades.append(trade)
        last_exit = exit_idx
    return trades


def _positive_ratio(per_asset: dict[str, dict]) -> float:
    return sum(value["net_return_pct"] > 0 for value in per_asset.values()) / len(per_asset)


def evaluate_params(frames: dict[str, pd.DataFrame], params: dict, config: dict,
                    signal_cache: dict | None = None, signal_start: str | None = None,
                    signal_end: str | None = None) -> dict:
    signal_cache = signal_cache if signal_cache is not None else {}
    trades_by_asset = {}
    for asset in ASSETS:
        key = (asset, *(params[name] for name in SIGNAL_KEYS))
        if key not in signal_cache:
            signal_cache[key] = entry_signal(frames[asset], params)
        trades_by_asset[asset] = simulate(
            frames[asset], {**params, "asset": asset}, config["cost_model"], config["small_account"],
            signal_start=signal_start, signal_end=signal_end, prepared=signal_cache[key])
    trades, skipped = schedule_portfolio(trades_by_asset, config["small_account"]["maximum_concurrent_positions"])
    scenarios = config["cost_model"]["scenarios"]
    measured = {name: metrics(trades, name) for name in scenarios}
    per_asset = {asset: {name: metrics([t for t in trades if t["asset"] == asset], name) for name in scenarios}
                 for asset in ASSETS}
    stress, gate = measured["stress"], config["pre_registered_discovery_gate"]
    stress_assets = {asset: values["stress"] for asset, values in per_asset.items()}
    expectancy_usdc = stress["expectancy_bps"] / 10_000 * config["small_account"]["capital_usdc"]
    liquidations = sum(trade["liquidation"] for trade in trades)
    passed = (stress["trades"] >= gate["minimum_portfolio_trades"]
              and all(value["trades"] >= gate["minimum_trades_per_asset"] for value in stress_assets.values())
              and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
              and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
              and _positive_ratio(stress_assets) >= gate["minimum_positive_asset_ratio"]
              and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
              and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
              and liquidations <= gate["maximum_liquidations"]
              and expectancy_usdc >= gate["minimum_net_expectancy_usdc"])
    return {"candidate_id": candidate_id(params), "parameters": params, "metrics": measured,
            "per_asset_metrics": per_asset, "positive_asset_ratio": _positive_ratio(stress_assets),
            "liquidations": liquidations, "stress_expectancy_usdc": expectancy_usdc,
            "trade_diagnostics": trade_diagnostics(trades), "scheduler_skips": len(skipped),
            "passes_point_gate": bool(passed)}


def stable_selection(config: dict, rows: list[dict]):
    passing = {row["candidate_id"]: row for row in rows if row["passes_point_gate"]}
    grid = config["grid"]
    lookup = {tuple(row["parameters"][key] for key in (*GROUP, *AXES)): row["candidate_id"] for row in rows}
    neighbours = {candidate: set() for candidate in passing}
    for candidate, row in passing.items():
        params = row["parameters"]
        for axis in AXES:
            values, at = grid[axis], grid[axis].index(params[axis])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(values):
                    altered = {**params, axis: values[other_at]}
                    other = lookup.get(tuple(altered[key] for key in (*GROUP, *AXES)))
                    if other in passing:
                        neighbours[candidate].add(other)
        row["passing_orthogonal_neighbours"] = len(neighbours[candidate])
    stable = {candidate for candidate, adjacent in neighbours.items()
              if len(adjacent) >= config["stability"]["minimum_passing_neighbours"]}
    selected = []
    for group in itertools.product(*(grid[key] for key in GROUP)):
        nodes = {candidate for candidate, row in passing.items()
                 if tuple(row["parameters"][key] for key in GROUP) == group}
        components = []
        while nodes:
            frontier, component = {min(nodes)}, set()
            while frontier:
                node = frontier.pop(); component.add(node); nodes.remove(node)
                frontier |= neighbours[node] & nodes
            if component & stable:
                components.append(component)
        if not components:
            continue
        component = sorted(components, key=lambda item: (-len(item), sorted(item)))[0]
        def distance(left, right):
            a, b = passing[left]["parameters"], passing[right]["parameters"]
            return sum(abs(grid[axis].index(a[axis]) - grid[axis].index(b[axis])) for axis in AXES)
        medoid = min(component, key=lambda item: (sum(distance(item, other) for other in component), item))
        selected.append({"candidate_id": medoid, "component_size": len(component),
                         "parameters": passing[medoid]["parameters"], "performance_metrics_used": False})
    return sorted(stable), selected


def run(sources: dict[str, Path], config: dict, temporal_gate: dict) -> dict:
    if temporal_gate["decision"] != "PASS_INTERNAL_NON_INDEPENDENT" or temporal_gate["performance_promotion_authorized"]:
        raise ValueError("TEMPORAL_GATE_NOT_INTERNAL_SAFE")
    frames = {asset: h4_frame(path, config["periods"]["discovery_from"], config["periods"]["discovery_to"])
              for asset, path in sources.items()}
    cache = {}
    rows = [evaluate_params(frames, params, config, cache) for params in parameter_grid(config)]
    stable, selected = stable_selection(config, rows)
    eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= config["pre_registered_discovery_gate"]["minimum_portfolio_trades"]]
    decision = "PASS_DISCOVERY_TO_INTERNAL_WF" if selected else "REJECT_CRYPTO_DONCHIAN_ATR_NO_STABLE_REGION"
    return {"schema_version": 1, "family_id": config["family_id"], "period": "discovery",
            "temporal_claim": "internal_non_independent",
            "source_sha256": {asset: file_sha256(path) for asset, path in sources.items()},
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]],
            "stable_candidate_ids": stable, "topology_selected_representatives": selected,
            "decision": decision, "stop_rule_triggered": not bool(selected),
            "stop_reason": None if selected else "No universal stable component passed the preregistered discovery gate.",
            "diagnostic_top_30": sorted(eligible, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:30],
            "internal_folds_accessed": False, "global_holdout_accessed": False,
            "sqcli_builder_executed": False, "performance_promotion_authorized": False,
            "paper_or_live_authorized": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--btc", type=Path, required=True); parser.add_argument("--eth", type=Path, required=True)
    parser.add_argument("--sol", type=Path, required=True); parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--temporal-gate", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run({"BTCUSD": args.btc, "ETHUSD": args.eth, "SOLUSD": args.sol},
                 json.loads(args.family.read_text()), json.loads(args.temporal_gate.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes",
                                                   "stable_candidate_ids", "topology_selected_representatives", "decision")}, indent=2))


if __name__ == "__main__":
    main()
