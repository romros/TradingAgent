#!/usr/bin/env python3
"""Deterministic, preregistered XAU D1 inside-day breakout preflight."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


PARAMETERS = ("side", "inside_range_ratio_max", "trend_ema", "atr_period",
              "entry_buffer_atr", "stop_atr", "target_atr", "hold_sessions")


def load_daily(root: Path, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    import duckdb
    pattern = str(root / "XAUUSD" / "tf=1m" / "year=*" / "month=*" / "data.parquet")
    where = ""
    if start is not None and end is not None:
        # Dates come from the tracked preregistration, not user SQL. Two buffer
        # days preserve the NY session at both boundaries while enabling Parquet
        # partition/predicate pruning.
        start_ts = int(pd.Timestamp(start, tz="UTC").timestamp()) - 2 * 86400
        end_ts = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp()) + 2 * 86400
        where = f"WHERE ts BETWEEN {start_ts} AND {end_ts}"
    sql = f"""
    WITH bars AS (
      SELECT *, (to_timestamp(ts) AT TIME ZONE 'America/New_York') AS ny
      FROM read_parquet('{pattern}')
      {where}
    ), labelled AS (
      SELECT *, CAST(ny + INTERVAL '7 hours' AS DATE) AS session_date FROM bars
    )
    SELECT session_date, arg_min(open, ts) AS open, max(high) AS high,
      min(low) AS low, arg_max(close, ts) AS close, count(*) AS bars
    FROM labelled GROUP BY session_date ORDER BY session_date
    """
    frame = duckdb.sql(sql).df().set_index("session_date")
    frame.index = pd.to_datetime(frame.index)
    return frame[(frame.open > 0) & (frame.high > 0) & (frame.low > 0) &
                 (frame.close > 0) & (frame.bars >= 60)].copy()


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    previous_close = out.close.shift(1)
    true_range = pd.concat([
        out.high - out.low,
        (out.high - previous_close).abs(),
        (out.low - previous_close).abs(),
    ], axis=1).max(axis=1)
    for period in (14, 28):
        out[f"atr_{period}"] = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    for period in (50, 200):
        out[f"ema_{period}"] = out.close.ewm(span=period, adjust=False, min_periods=period).mean()
    out["inside"] = (out.high < out.high.shift(1)) & (out.low > out.low.shift(1))
    out["range_ratio"] = (out.high - out.low) / (out.high.shift(1) - out.low.shift(1))
    return out


def simulate(frame: pd.DataFrame, params: dict, costs: dict) -> list[dict]:
    trades = []
    side = params["side"]
    atr_col = f"atr_{params['atr_period']}"
    opened = frame.open.to_numpy()
    high = frame.high.to_numpy()
    low = frame.low.to_numpy()
    close = frame.close.to_numpy()
    inside = frame.inside.to_numpy()
    range_ratio = frame.range_ratio.to_numpy()
    atr_values = frame[atr_col].to_numpy()
    ema_values = frame[f"ema_{params['trend_ema']}"] .to_numpy() if params["trend_ema"] else None
    dates = frame.index
    last_exit_idx = -1
    for signal_idx in range(1, len(frame) - 1):
        if signal_idx + 1 <= last_exit_idx:
            continue
        if not inside[signal_idx] or range_ratio[signal_idx] > params["inside_range_ratio_max"]:
            continue
        atr = atr_values[signal_idx]
        if not np.isfinite(atr) or atr <= 0:
            continue
        ema_period = params["trend_ema"]
        if ema_period:
            ema = ema_values[signal_idx]
            if not np.isfinite(ema) or (side == "long" and close[signal_idx] <= ema) or (side == "short" and close[signal_idx] >= ema):
                continue
        direction = 1 if side == "long" else -1
        trigger = high[signal_idx] + params["entry_buffer_atr"] * atr if direction == 1 else low[signal_idx] - params["entry_buffer_atr"] * atr
        entry_idx = signal_idx + 1
        touched = high[entry_idx] >= trigger if direction == 1 else low[entry_idx] <= trigger
        if not touched:
            continue
        entry = max(opened[entry_idx], trigger) if direction == 1 else min(opened[entry_idx], trigger)
        stop = entry - direction * params["stop_atr"] * atr
        target = entry + direction * params["target_atr"] * atr
        exit_price = None
        exit_idx = min(entry_idx + params["hold_sessions"] - 1, len(frame) - 1)
        reason = "time"
        ambiguous = False
        for bar_idx in range(entry_idx, exit_idx + 1):
            stop_hit = low[bar_idx] <= stop if direction == 1 else high[bar_idx] >= stop
            target_hit = high[bar_idx] >= target if direction == 1 else low[bar_idx] <= target
            if stop_hit and target_hit:
                ambiguous = True
                target_hit = False
            if stop_hit:
                exit_price = min(opened[bar_idx], stop) if direction == 1 else max(opened[bar_idx], stop)
                exit_idx, reason = bar_idx, "stop"
                break
            if target_hit:
                exit_price = max(opened[bar_idx], target) if direction == 1 else min(opened[bar_idx], target)
                exit_idx, reason = bar_idx, "target"
                break
        if exit_price is None:
            exit_price = close[exit_idx]
        gross = direction * (exit_price / entry - 1)
        elapsed_days = max((dates[exit_idx] - dates[entry_idx]).total_seconds() / 86400, 0) + 1
        trade = {"entry_date": str(dates[entry_idx].date()), "exit_date": str(dates[exit_idx].date()),
                 "gross_return": gross, "ambiguous": ambiguous, "reason": reason}
        for name, cost in costs.items():
            trade[name] = gross - cost["opening_bps"] / 10_000 - cost["annual_funding_pct"] / 100 * elapsed_days / 365.25
        trades.append(trade)
        last_exit_idx = exit_idx
    return trades


def metrics(trades: list[dict], scenario: str) -> dict:
    values = np.array([trade[scenario] for trade in trades], dtype=float)
    wins = values[values > 0].sum() if len(values) else 0
    losses = -values[values < 0].sum() if len(values) else 0
    years: dict[int, float] = {}
    for trade, value in zip(trades, values):
        year = int(trade["exit_date"][:4])
        years[year] = (1 + years.get(year, 0)) * (1 + value) - 1
    equity = np.cumprod(1 + values) if len(values) else np.array([])
    peak = np.maximum.accumulate(np.r_[1.0, equity])
    drawdown = 1 - np.r_[1.0, equity] / peak
    return {
        "trades": len(trades),
        "profit_factor": round(float(wins / losses), 6) if losses else (999.0 if wins else 0.0),
        "net_return_pct": round(float((equity[-1] - 1) * 100), 6) if len(equity) else 0.0,
        "max_drawdown_pct": round(float(drawdown.max() * 100), 6),
        "positive_year_ratio": round(sum(value > 0 for value in years.values()) / len(years), 6) if years else 0.0,
        "year_returns_pct": {str(year): round(value * 100, 4) for year, value in sorted(years.items())},
        "expectancy_bps": round(float(values.mean() * 10_000), 6) if len(values) else 0.0,
    }


def parameter_grid(config: dict):
    grid = config["pre_registered_grid"]
    values = [grid[name] for name in PARAMETERS]
    for row in itertools.product(*values):
        yield dict(zip(PARAMETERS, row))


def candidate_id(params: dict) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return "v9-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def run(root: Path, config: dict, period: str = "train") -> dict:
    if period != "train":
        raise ValueError("PREFLIGHT_ONLY_ALLOWS_TRAIN; freeze finalists before validation")
    start, end = config["periods"]["train_from"], config["periods"]["train_to"]
    full = enrich(load_daily(root, start, end))
    frame = full.loc[start:end]
    falsifiers = config["pre_registered_falsifiers"]
    rows = []
    for params in parameter_grid(config):
        trades = simulate(frame, params, config["costs"])
        result = {name: metrics(trades, name) for name in config["costs"]}
        passed = bool(result["base"]["trades"] >= falsifiers["minimum_train_trades"] and
                  result["base"]["profit_factor"] >= falsifiers["minimum_base_profit_factor"] and
                  result["stress"]["profit_factor"] >= falsifiers["minimum_stress_profit_factor"] and
                  result["stress"]["positive_year_ratio"] >= falsifiers["minimum_positive_year_ratio"])
        rows.append({"candidate_id": candidate_id(params), "parameters": params, "metrics": result,
                     "ambiguous_trades": sum(t["ambiguous"] for t in trades), "passes_point_gate": passed})
    passing_keys = {tuple(row["parameters"][name] for name in PARAMETERS) for row in rows if row["passes_point_gate"]}
    grids = config["pre_registered_grid"]
    for row in rows:
        params = row["parameters"]
        neighbours = 0
        for name in PARAMETERS[1:]:
            options = grids[name]
            at = options.index(params[name])
            for other_at in (at - 1, at + 1):
                if 0 <= other_at < len(options):
                    altered = dict(params); altered[name] = options[other_at]
                    key = tuple(altered[field] for field in PARAMETERS)
                    neighbours += key in passing_keys
        row["passing_orthogonal_neighbours"] = neighbours
        row["stable"] = bool(row["passes_point_gate"] and neighbours >= falsifiers["minimum_passing_orthogonal_neighbours"])
    stable = [row["candidate_id"] for row in rows if row["stable"]]
    grid_sha256 = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    diagnostic_pool = [row for row in rows if row["metrics"]["base"]["trades"] >= falsifiers["minimum_train_trades"]]
    diagnostics = sorted(
        diagnostic_pool,
        key=lambda row: (row["metrics"]["stress"]["profit_factor"], row["metrics"]["stress"]["expectancy_bps"]),
        reverse=True,
    )[:20]
    return {
        "schema_version": 1, "family_id": config["family_id"], "period": period,
        "source": "BrokerageService Dukascopy XAUUSD M1 parquet aggregated to DST-aware NY-close D1",
        "coverage": {"from": str(frame.index.min().date()), "to": str(frame.index.max().date()), "sessions": len(frame)},
        "points_evaluated": len(rows), "point_gate_passes": sum(r["passes_point_gate"] for r in rows),
        "stable_candidate_ids": stable, "holdout_accessed": False,
        "evaluated_grid_sha256": grid_sha256,
        "diagnostic_top_20_by_stress_profit_factor": diagnostics,
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
