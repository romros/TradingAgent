#!/usr/bin/env python3
"""Preregistered, train-only BTC multi-mechanism falsification screen."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.binance_sq_source import file_sha256


def load_m1(path: Path, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    names = ["date", "time", "open", "high", "low", "close", "volume"]
    first = pd.Timestamp(start, tz="UTC") if start else None
    last = (pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)) if end else None
    selected = []
    for frame in pd.read_csv(path, names=names, dtype={"date": str, "time": str}, chunksize=250_000):
        index = pd.DatetimeIndex(pd.to_datetime(frame.pop("date") + " " + frame.pop("time"), format="%Y.%m.%d %H:%M", utc=True))
        frame.index = index
        if last is not None and index.min() > last:
            break
        mask = np.ones(len(index), dtype=bool)
        if first is not None: mask &= index >= first
        if last is not None: mask &= index <= last
        if mask.any(): selected.append(frame.loc[mask])
    if not selected:
        raise ValueError("NO_M1_IN_REQUESTED_PERIOD")
    frame = pd.concat(selected)
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise ValueError("M1_TIMESTAMPS_NOT_UNIQUE_AND_ORDERED")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("NON_POSITIVE_PRICE")
    return frame


def aggregate(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    rule = {"H1": "1h", "H4": "4h", "D1": "1D"}[timeframe]
    resampler = frame.resample(rule, label="left", closed="left", **({"origin": "epoch"} if timeframe != "D1" else {}))
    out = resampler.agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), source_bars=("close", "count"))
    expected = {"H1": 60, "H4": 240, "D1": 1440}[timeframe]
    out["complete"] = out.source_bars == expected
    return out.dropna(subset=["open", "high", "low", "close"])


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    prior = out.close.shift(1)
    tr = pd.concat([out.high - out.low, (out.high - prior).abs(), (out.low - prior).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    for period in (50, 100, 200):
        out[f"ema_{period}"] = out.close.ewm(span=period, adjust=False, min_periods=period).mean()
    delta = out.close.diff(); gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    for period in (2, 3, 5):
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        out[f"rsi_{period}"] = 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def signals(frame: pd.DataFrame, mechanism: str, params: dict) -> tuple[pd.Series, pd.Series | None]:
    side = params["side"]
    if mechanism == "donchian_trend":
        valid = frame.complete.rolling(max(params["lookback"], params["exit_lookback"])).min().fillna(False).astype(bool)
        high = frame.high.shift(1).rolling(params["lookback"]).max()
        low = frame.low.shift(1).rolling(params["lookback"]).min()
        entry = frame.close > high if side == "long" else frame.close < low
        exit_high = frame.high.shift(1).rolling(params["exit_lookback"]).max()
        exit_low = frame.low.shift(1).rolling(params["exit_lookback"]).min()
        exit_signal = frame.close < exit_low if side == "long" else frame.close > exit_high
        return entry & valid, exit_signal & frame.complete
    if mechanism == "regime_donchian":
        valid = frame.complete.rolling(max(params["lookback"], params["exit_lookback"])).min().fillna(False).astype(bool)
        high = frame.high.shift(1).rolling(params["lookback"]).max()
        low = frame.low.shift(1).rolling(params["lookback"]).min()
        regime = frame[f"regime_{params['regime_ema']}"]
        entry = ((frame.close > high) & (regime > 0)) if side == "long" else ((frame.close < low) & (regime < 0))
        exit_high = frame.high.shift(1).rolling(params["exit_lookback"]).max()
        exit_low = frame.low.shift(1).rolling(params["exit_lookback"]).min()
        exit_signal = frame.close < exit_low if side == "long" else frame.close > exit_high
        return entry & valid & regime.notna(), exit_signal & frame.complete
    if mechanism == "trend_pullback":
        valid = frame.complete.rolling(max(params["trend_ema"], params["rsi_period"])).min().fillna(False).astype(bool)
        ema, rsi = frame[f"ema_{params['trend_ema']}"] , frame[f"rsi_{params['rsi_period']}"]
        entry = ((frame.close > ema) & (rsi <= params["rsi_extreme"])) if side == "long" else ((frame.close < ema) & (rsi >= 100 - params["rsi_extreme"]))
        return entry & valid, None
    if mechanism == "compression_breakout":
        valid = frame.complete.rolling(max(params["atr_rank_lookback"] + 3, params["channel_lookback"])).min().fillna(False).astype(bool)
        rank = frame.atr.rolling(params["atr_rank_lookback"]).rank(pct=True)
        armed = rank.shift(1).rolling(3).min() <= params["compression_quantile"]
        high = frame.high.shift(1).rolling(params["channel_lookback"]).max()
        low = frame.low.shift(1).rolling(params["channel_lookback"]).min()
        entry = armed & ((frame.close > high) if side == "long" else (frame.close < low))
        return entry & valid, None
    raise ValueError(f"UNKNOWN_MECHANISM:{mechanism}")


def simulate(frame: pd.DataFrame, mechanism: str, params: dict, costs: dict,
             signal_start: str | None = None, signal_end: str | None = None) -> list[dict]:
    entry_signal, exit_signal = signals(frame, mechanism, params)
    direction = 1 if params["side"] == "long" else -1
    opened, high, low, close, atr = (frame[name].to_numpy() for name in ("open", "high", "low", "close", "atr"))
    complete = frame.complete.to_numpy(); entries = entry_signal.fillna(False).to_numpy()
    exits = exit_signal.fillna(False).to_numpy() if exit_signal is not None else None
    dates = frame.index; last_exit = -1; trades = []
    allowed_start = pd.Timestamp(signal_start, tz="UTC") if signal_start else None
    allowed_end = pd.Timestamp(signal_end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1) if signal_end else None
    for signal_idx in np.flatnonzero(entries):
        if allowed_start is not None and dates[signal_idx] < allowed_start: continue
        if allowed_end is not None and dates[signal_idx] > allowed_end: continue
        entry_idx = signal_idx + 1
        if entry_idx >= len(frame) or (allowed_end is not None and dates[entry_idx] > allowed_end) or entry_idx <= last_exit or not complete[signal_idx] or not complete[entry_idx] or not np.isfinite(atr[signal_idx]):
            continue
        entry = opened[entry_idx]; stop = entry - direction * params["stop_atr"] * atr[signal_idx]
        if mechanism in ("donchian_trend", "regime_donchian"):
            future = np.flatnonzero(exits[entry_idx:])
            planned = entry_idx + int(future[0]) + 1 if len(future) else len(frame) - 1
        else:
            planned = min(entry_idx + params["hold_bars"] - 1, len(frame) - 1)
        exit_idx = min(planned, len(frame) - 1); exit_price = None; reason = "signal" if mechanism == "donchian_trend" else "time"
        invalid = False
        for bar_idx in range(entry_idx, exit_idx + 1):
            if not complete[bar_idx]:
                exit_idx = bar_idx; invalid = True; break
            hit = low[bar_idx] <= stop if direction == 1 else high[bar_idx] >= stop
            if hit:
                exit_idx = bar_idx; exit_price = min(opened[bar_idx], stop) if direction == 1 else max(opened[bar_idx], stop); reason = "stop"; break
        if invalid:
            last_exit = exit_idx
            continue
        if exit_price is None:
            exit_price = opened[exit_idx] if mechanism in ("donchian_trend", "regime_donchian") else close[exit_idx]
        gross = direction * (exit_price / entry - 1)
        days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0)
        trade = {"entry": dates[entry_idx].isoformat(), "exit": dates[exit_idx].isoformat(), "gross": gross,
                 "stop_distance": abs(entry - stop) / entry, "reason": reason}
        for name, scenario in costs["scenarios"].items():
            variable_bps = costs["ostium_opening_fee_bps"] + scenario["dynamic_spread_and_impact_bps"]
            trade[name] = gross - variable_bps / 10_000 - scenario["annual_rollover_pct"] / 100 * days / 365.25
        trades.append(trade); last_exit = exit_idx
    return trades


def metrics(trades: list[dict], scenario: str) -> dict:
    values = np.asarray([trade[scenario] for trade in trades], dtype=float)
    if not len(values):
        return {"trades": 0, "profit_factor": 0, "expectancy_bps": 0, "net_return_pct": 0, "drawdown_pct": 0,
                "positive_year_ratio": 0, "positive_half_year_ratio": 0, "positive_quarter_ratio": 0}
    wins, losses = values[values > 0].sum(), -values[values < 0].sum()
    equity = np.cumprod(1 + values); peak = np.maximum.accumulate(np.r_[1.0, equity])
    drawdown = 1 - np.r_[1.0, equity] / peak
    years, halves, quarters = {}, {}, {}
    for trade, value in zip(trades, values):
        years.setdefault(trade["entry"][:4], []).append(value)
        halves.setdefault(trade["entry"][:4] + ("-H1" if int(trade["entry"][5:7]) <= 6 else "-H2"), []).append(value)
        month = int(trade["entry"][5:7]); quarters.setdefault(f"{trade['entry'][:4]}-Q{(month - 1) // 3 + 1}", []).append(value)
    return {"trades": len(values), "profit_factor": float(wins / losses) if losses else 999.0,
            "expectancy_bps": float(values.mean() * 10_000), "net_return_pct": float((equity[-1] - 1) * 100),
            "drawdown_pct": float(drawdown.max() * 100),
            "positive_year_ratio": sum(np.prod(1 + np.asarray(v)) > 1 for v in years.values()) / len(years),
            "positive_half_year_ratio": sum(np.prod(1 + np.asarray(v)) > 1 for v in halves.values()) / len(halves),
            "positive_quarter_ratio": sum(np.prod(1 + np.asarray(v)) > 1 for v in quarters.values()) / len(quarters)}


def grids(config: dict):
    for mechanism, spec in config["families"].items():
        for timeframe in spec["timeframes"]:
            keys = [key for key in spec if key != "timeframes"]
            for values in itertools.product(*(spec[key] for key in keys)):
                params = dict(zip(("side" if key == "sides" else key for key in keys), values)); params["timeframe"] = timeframe
                yield mechanism, params


def candidate_id(mechanism: str, params: dict) -> str:
    raw = json.dumps({"mechanism": mechanism, **params}, sort_keys=True, separators=(",", ":"))
    return "v11-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def stable_regions(config: dict, rows: list[dict]) -> tuple[list[str], list[dict]]:
    passing = {row["candidate_id"]: row for row in rows if row["passes_point_gate"]}
    by_identity = {(row["mechanism"], tuple(sorted(row["parameters"].items()))): row["candidate_id"] for row in rows}
    neighbours: dict[str, set[str]] = {candidate: set() for candidate in passing}
    for candidate, row in passing.items():
        mechanism, params = row["mechanism"], row["parameters"]
        spec = config["families"][mechanism]
        for config_key, options in spec.items():
            if config_key in ("timeframes", "sides"):
                continue
            at = options.index(params[config_key])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(options):
                    altered = dict(params); altered[config_key] = options[other_at]
                    other = by_identity.get((mechanism, tuple(sorted(altered.items()))))
                    if other in passing: neighbours[candidate].add(other)
        row["passing_orthogonal_neighbours"] = len(neighbours[candidate])
    minimum = config["pre_registered_train_gate"]["minimum_passing_orthogonal_neighbours"]
    stable = {candidate for candidate, adjacent in neighbours.items() if len(adjacent) >= minimum}
    representatives = []
    groups = sorted({(row["mechanism"], row["parameters"]["timeframe"], row["parameters"]["side"])
                     for row in passing.values()})
    for group in groups:
        nodes = {candidate for candidate in passing if (passing[candidate]["mechanism"], passing[candidate]["parameters"]["timeframe"], passing[candidate]["parameters"]["side"]) == group}
        components = []
        while nodes:
            frontier = {min(nodes)}; component = set()
            while frontier:
                node = frontier.pop(); component.add(node); nodes.remove(node)
                frontier |= (neighbours[node] & nodes)
            components.append(component)
        components = [component for component in components if component & stable]
        if not components: continue
        component = sorted(components, key=lambda item: (-len(item), sorted(item)))[0]
        def distance(left: str, right: str) -> int:
            a, b = passing[left]["parameters"], passing[right]["parameters"]
            spec = config["families"][group[0]]
            return sum(abs(spec[key].index(a[key]) - spec[key].index(b[key])) for key in spec if key not in ("timeframes", "sides"))
        medoid = min(component, key=lambda candidate: (sum(distance(candidate, other) for other in component), candidate))
        representatives.append({"mechanism": group[0], "timeframe": group[1], "side": group[2],
                                "component_size": len(component), "candidate_id": medoid,
                                "parameters": passing[medoid]["parameters"], "performance_metrics_used": False})
    return sorted(stable), representatives


def run(source: Path, config: dict) -> dict:
    start, end = config["periods"]["train_from"], config["periods"]["train_to"]
    raw = load_m1(source, start, end)
    frames = {tf: enrich(aggregate(raw, tf)) for tf in ("H1", "H4", "D1")}
    gate = config["pre_registered_train_gate"]; rows = []
    for mechanism, params in grids(config):
        trades = simulate(frames[params["timeframe"]], mechanism, params, config["cost_model"])
        result = {name: metrics(trades, name) for name in config["cost_model"]["scenarios"]}
        stress = result["stress"]
        passed = stress["trades"] >= gate["minimum_trades"] and stress["profit_factor"] >= gate["minimum_stress_profit_factor"] and stress["expectancy_bps"] >= gate["minimum_stress_expectancy_bps"] and stress["positive_year_ratio"] >= gate["minimum_positive_year_ratio"] and stress["drawdown_pct"] <= gate["maximum_stress_drawdown_pct"]
        rows.append({"candidate_id": candidate_id(mechanism, params), "mechanism": mechanism, "parameters": params,
                     "metrics": result, "passes_point_gate": bool(passed)})
    stable, representatives = stable_regions(config, rows)
    diagnostic_pool = [row for row in rows if row["metrics"]["stress"]["trades"] >= gate["minimum_trades"]]
    diagnostics = sorted(diagnostic_pool, key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]), reverse=True)[:30]
    return {"schema_version": 1, "family_id": config["family_id"], "period": "train", "source_csv": str(source),
            "source_sha256": file_sha256(source), "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "coverage": {tf: {"from": frame.index.min().isoformat(), "to": frame.index.max().isoformat(), "bars": len(frame), "incomplete_bars": int((~frame.complete).sum())} for tf, frame in frames.items()},
            "points_evaluated": len(rows), "point_gate_passes": sum(row["passes_point_gate"] for row in rows),
            "passing_candidates": [row for row in rows if row["passes_point_gate"]], "stable_candidate_ids": stable,
            "topology_selected_representatives": representatives, "diagnostic_top_30": diagnostics,
            "holdout_accessed": False, "sqcli_executed": False, "paper_or_live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--family", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); config = json.loads(args.family.read_text()); result = run(args.source, config)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("family_id", "coverage", "points_evaluated", "point_gate_passes", "holdout_accessed")}, indent=2))


if __name__ == "__main__": main()
