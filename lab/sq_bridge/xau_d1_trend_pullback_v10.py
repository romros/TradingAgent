#!/usr/bin/env python3
"""Preregistered train-only XAU D1 trend-pullback preflight."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.xau_d1_inside_breakout_v9 import load_daily, metrics


PARAMETERS = ("side", "trend_ema", "rsi_period", "rsi_extreme", "stop_atr", "hold_sessions")


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    previous_close = out.close.shift(1)
    true_range = pd.concat([
        out.high - out.low,
        (out.high - previous_close).abs(),
        (out.low - previous_close).abs(),
    ], axis=1).max(axis=1)
    out["atr_14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    for period in (100, 200):
        out[f"ema_{period}"] = out.close.ewm(span=period, adjust=False, min_periods=period).mean()
    delta = out.close.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    for period in (2, 3, 5):
        average_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        average_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = average_gain / average_loss
        out[f"rsi_{period}"] = 100 - 100 / (1 + rs)
    return out


def simulate(frame: pd.DataFrame, params: dict, costs: dict) -> list[dict]:
    side = params["side"]
    direction = 1 if side == "long" else -1
    opened, high, low, close = (frame[name].to_numpy() for name in ("open", "high", "low", "close"))
    atr = frame.atr_14.to_numpy()
    ema = frame[f"ema_{params['trend_ema']}"] .to_numpy()
    rsi = frame[f"rsi_{params['rsi_period']}"] .to_numpy()
    dates = frame.index
    last_exit_idx = -1
    trades = []
    for signal_idx in range(len(frame) - 1):
        entry_idx = signal_idx + 1
        if entry_idx <= last_exit_idx or not all(np.isfinite(value) for value in (atr[signal_idx], ema[signal_idx], rsi[signal_idx])):
            continue
        if side == "long":
            setup = close[signal_idx] > ema[signal_idx] and rsi[signal_idx] <= params["rsi_extreme"]
        else:
            setup = close[signal_idx] < ema[signal_idx] and rsi[signal_idx] >= 100 - params["rsi_extreme"]
        if not setup:
            continue
        entry = opened[entry_idx]
        stop = entry - direction * params["stop_atr"] * atr[signal_idx]
        exit_idx = min(entry_idx + params["hold_sessions"] - 1, len(frame) - 1)
        exit_price, reason = None, "time"
        for bar_idx in range(entry_idx, exit_idx + 1):
            stop_hit = low[bar_idx] <= stop if direction == 1 else high[bar_idx] >= stop
            if stop_hit:
                exit_price = min(opened[bar_idx], stop) if direction == 1 else max(opened[bar_idx], stop)
                exit_idx, reason = bar_idx, "stop"
                break
        if exit_price is None:
            exit_price = close[exit_idx]
        gross = direction * (exit_price / entry - 1)
        elapsed_days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0) + 1
        trade = {"entry_date": str(dates[entry_idx].date()), "exit_date": str(dates[exit_idx].date()),
                 "gross_return": gross, "reason": reason}
        for name, cost in costs.items():
            trade[name] = gross - cost["opening_bps"] / 10_000 - cost["annual_funding_pct"] / 100 * elapsed_days / 365.25
        trades.append(trade)
        last_exit_idx = exit_idx
    return trades


def parameter_grid(config: dict):
    grid = config["pre_registered_grid"]
    for values in itertools.product(*(grid[name] for name in PARAMETERS)):
        yield dict(zip(PARAMETERS, values))


def candidate_id(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return "v10-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def run(root: Path, config: dict, period: str = "train") -> dict:
    if period != "train":
        raise ValueError("PREFLIGHT_ONLY_ALLOWS_TRAIN; freeze finalists before validation")
    start, end = config["periods"]["train_from"], config["periods"]["train_to"]
    frame = enrich(load_daily(root, start, end)).loc[start:end]
    gate = config["pre_registered_falsifiers"]
    rows = []
    for params in parameter_grid(config):
        trades = simulate(frame, params, config["costs"])
        result = {name: metrics(trades, name) for name in config["costs"]}
        passed = bool(result["base"]["trades"] >= gate["minimum_train_trades"] and
                  result["base"]["profit_factor"] >= gate["minimum_base_profit_factor"] and
                  result["stress"]["profit_factor"] >= gate["minimum_stress_profit_factor"] and
                  result["stress"]["positive_year_ratio"] >= gate["minimum_positive_year_ratio"])
        rows.append({"candidate_id": candidate_id(params), "parameters": params,
                     "metrics": result, "passes_point_gate": passed})
    passing = {tuple(row["parameters"][name] for name in PARAMETERS) for row in rows if row["passes_point_gate"]}
    grid = config["pre_registered_grid"]
    for row in rows:
        params, neighbours = row["parameters"], 0
        for name in PARAMETERS[1:]:
            options, at = grid[name], grid[name].index(params[name])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(options):
                    altered = dict(params); altered[name] = options[other_at]
                    neighbours += tuple(altered[field] for field in PARAMETERS) in passing
        row["passing_orthogonal_neighbours"] = neighbours
        row["stable"] = bool(row["passes_point_gate"] and neighbours >= gate["minimum_passing_orthogonal_neighbours"])
    stable = [row["candidate_id"] for row in rows if row["stable"]]
    grid_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    diagnostic_pool = [row for row in rows if row["metrics"]["base"]["trades"] >= gate["minimum_train_trades"]]
    diagnostics = sorted(diagnostic_pool, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:20]
    return {
        "schema_version": 1, "family_id": config["family_id"], "period": period,
        "source": "BrokerageService Dukascopy XAUUSD M1 parquet aggregated to DST-aware NY-close D1",
        "coverage": {"from": str(frame.index.min().date()), "to": str(frame.index.max().date()), "sessions": len(frame)},
        "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
        "stable_candidate_ids": stable, "holdout_accessed": False,
        "evaluated_grid_sha256": grid_hash, "diagnostic_top_20_by_stress_profit_factor": diagnostics,
        "stable_candidates": [row for row in rows if row["stable"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, json.loads(args.family.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "coverage", "points_evaluated", "point_gate_passes", "stable_candidate_ids", "holdout_accessed")}, indent=2))


if __name__ == "__main__":
    main()
