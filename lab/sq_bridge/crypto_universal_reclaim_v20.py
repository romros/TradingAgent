#!/usr/bin/env python3
"""V20: one volatility-normalised reclaim rule across BTC, ETH and SOL."""
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
from lab.sq_bridge.crypto_capitulation_reclaim_v19 import simulate
from lab.sq_bridge.crypto_intraday_compression_v18 import hourly, trade_diagnostics


ASSETS = ("BTCUSD", "ETHUSD", "SOLUSD")
AXES = ("shock_close_atr", "range_atr", "reclaim_hours", "reclaim_fraction", "stop_atr", "hold_bars")
GROUP = ("side", "session_start_utc", "day_group")
SIGNAL_KEYS = (*GROUP, "shock_close_atr", "range_atr", "reclaim_hours", "reclaim_fraction")


def parameter_grid(config: dict):
    grid = config["grid"]
    keys = tuple(key for key in grid if key != "points")
    for values in itertools.product(*(grid[key] for key in keys)):
        yield dict(zip(keys, values))


def candidate_id(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return "v20-" + hashlib.sha256(raw).hexdigest()[:12]


def universal_reclaim_signals(frame: pd.DataFrame, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """Detect a shock in prior-ATR units and a later close reclaim."""
    count = len(frame)
    signals = np.zeros(count, dtype=bool)
    shock_atr = np.full(count, np.nan)
    close, high, low, complete, atr = (frame[name].to_numpy() for name in ("close", "high", "low", "complete", "atr"))
    prior_close = np.r_[np.nan, close[:-1]]
    prior_atr = np.r_[np.nan, atr[:-1]]
    close_change_atr = (close - prior_close) / prior_atr
    true_range = np.maximum(high - low, np.maximum(abs(high - prior_close), abs(low - prior_close)))
    direction = 1 if params["side"] == "long" else -1
    shock = close_change_atr <= -params["shock_close_atr"] if direction == 1 else close_change_atr >= params["shock_close_atr"]
    shock &= true_range >= params["range_atr"] * prior_atr
    shock &= complete & np.isfinite(prior_atr) & (prior_atr > 0)
    shock &= ((frame.index.hour // 8) * 8 == params["session_start_utc"])
    weekday = frame.index.dayofweek < 5
    shock &= weekday if params["day_group"] == "weekday" else ~weekday
    for at in np.flatnonzero(shock):
        if direction == 1:
            level = low[at] + params["reclaim_fraction"] * (high[at] - low[at])
        else:
            level = high[at] - params["reclaim_fraction"] * (high[at] - low[at])
        end = min(at + params["reclaim_hours"], count - 1)
        for trigger in range(at + 1, end + 1):
            if not complete[trigger]:
                break
            reclaimed = close[trigger] >= level if direction == 1 else close[trigger] <= level
            if reclaimed:
                if not signals[trigger]:
                    signals[trigger], shock_atr[trigger] = True, prior_atr[at]
                break
    return signals, shock_atr


def schedule_portfolio(trades_by_asset: dict[str, list[dict]], maximum_concurrent: int = 2) -> tuple[list[dict], list[dict]]:
    """Accept trades deterministically; exits at an entry instant free a slot."""
    proposals = []
    for asset, trades in trades_by_asset.items():
        proposals.extend({**trade, "asset": asset} for trade in trades)
    proposals.sort(key=lambda trade: (trade["entry"], trade["asset"], trade["exit"]))
    accepted, skipped, active = [], [], []
    for trade in proposals:
        entry = pd.Timestamp(trade["entry"])
        active = [item for item in active if pd.Timestamp(item["exit"]) > entry]
        if len(active) >= maximum_concurrent:
            skipped.append({"asset": trade["asset"], "entry": trade["entry"], "reason": "concurrency_cap"})
            continue
        accepted.append(trade)
        active.append(trade)
    return accepted, skipped


def _positive_ratio(per_asset: dict[str, dict]) -> float:
    return sum(value["net_return_pct"] > 0 for value in per_asset.values()) / len(per_asset)


def evaluate_params(frames: dict[str, pd.DataFrame], params: dict, config: dict,
                    signal_cache: dict | None = None) -> dict:
    signal_cache = signal_cache if signal_cache is not None else {}
    trades_by_asset = {}
    for asset in ASSETS:
        key = (asset, *(params[name] for name in SIGNAL_KEYS))
        if key not in signal_cache:
            signal_cache[key] = universal_reclaim_signals(frames[asset], params)
        asset_params = {**params, "asset": asset}
        trades_by_asset[asset] = simulate(
            frames[asset], asset_params, config["cost_model"], config["small_account"], prepared=signal_cache[key]
        )
    trades, skipped = schedule_portfolio(trades_by_asset, config["small_account"]["maximum_concurrent_positions"])
    measured = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}
    per_asset = {
        asset: {name: metrics([trade for trade in trades if trade["asset"] == asset], name)
                for name in config["cost_model"]["scenarios"]}
        for asset in ASSETS
    }
    stress = measured["stress"]
    gate = config["pre_registered_discovery_gate"]
    expectancy_usdc = stress["expectancy_bps"] / 10_000 * config["small_account"]["capital_usdc"]
    stress_assets = {asset: values["stress"] for asset, values in per_asset.items()}
    liquidations = sum(trade["liquidation"] for trade in trades)
    passed = (
        stress["trades"] >= gate["minimum_portfolio_trades"]
        and all(value["trades"] >= gate["minimum_trades_per_asset"] for value in stress_assets.values())
        and stress["profit_factor"] >= gate["minimum_stress_profit_factor"]
        and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps_on_capital"]
        and _positive_ratio(stress_assets) >= gate["minimum_positive_asset_ratio"]
        and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"]
        and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct_on_capital"]
        and liquidations <= gate["maximum_liquidations"]
        and expectancy_usdc >= gate["minimum_net_expectancy_usdc"]
    )
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
            values = grid[axis]
            at = values.index(params[axis])
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
    frames = {asset: hourly(path, config["periods"]["discovery_from"], config["periods"]["discovery_to"])
              for asset, path in sources.items()}
    cache = {}
    rows = [evaluate_params(frames, params, config, cache) for params in parameter_grid(config)]
    stable, selected = stable_selection(config, rows)
    eligible = [row for row in rows if row["metrics"]["stress"]["trades"] >= config["pre_registered_discovery_gate"]["minimum_portfolio_trades"]]
    decision = "PASS_DISCOVERY_TO_INTERNAL_WF" if selected else "REJECT_CRYPTO_UNIVERSAL_RECLAIM_NO_STABLE_REGION"
    return {"schema_version": 1, "family_id": config["family_id"], "period": "discovery",
            "temporal_claim": "internal_non_independent",
            "source_sha256": {asset: file_sha256(path) for asset, path in sources.items()},
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]],
            "stable_candidate_ids": stable, "topology_selected_representatives": selected,
            "decision": decision,
            "stop_rule_triggered": not bool(selected),
            "stop_reason": None if selected else "No point-gate candidate had the two preregistered passing orthogonal neighbours.",
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
    print(json.dumps({key: result[key] for key in ("family_id", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "topology_selected_representatives")}, indent=2))


if __name__ == "__main__":
    main()
