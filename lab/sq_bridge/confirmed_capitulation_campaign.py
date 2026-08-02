#!/usr/bin/env python3
"""Preregistered close-only confirmed-capitulation falsification campaign."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "lab" / "out" / "alquimia"
SPLITS = {
    "train": ("2004-01-01", "2013-12-31"),
    "validation": ("2014-01-01", "2018-12-31"),
    "oos": ("2019-01-01", "2023-12-31"),
    "holdout": ("2024-01-01", "2026-08-01"),
}
ASSETS = ("MSFT", "NVDA", "QQQ")
GRID = tuple(itertools.product((1.5, 2.0, 2.5), (.25, .50), (1, 2, 3), (False, True)))


def download(asset: str) -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(asset, start="2003-01-01", end="2026-08-02", auto_adjust=True,
                        actions=False, progress=False)
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    return frame[["open", "high", "low", "close"]].dropna().astype(float)


def trades(frame: pd.DataFrame, params: tuple[float, float, int, bool]) -> pd.DataFrame:
    z_limit, recovery, hold, regime = params
    close = frame.close
    daily_return = close.pct_change()
    sigma = daily_return.rolling(20).std(ddof=0).shift(1)
    drop = (sigma > 0) & (daily_return < 0) & (daily_return <= -z_limit * sigma)
    if regime:
        drop &= close.shift(1) > close.shift(1).rolling(200).mean()
    loss = close.shift(1) - close
    confirmed = drop.shift(1).fillna(False) & (close - close.shift(1) >= recovery * loss.shift(1))
    rows = []
    indices = np.flatnonzero(confirmed.to_numpy())
    last_exit = -1
    for entry_i in indices:
        exit_i = entry_i + hold
        if entry_i <= last_exit or exit_i >= len(frame):
            continue
        entry, exit_ = float(close.iloc[entry_i]), float(close.iloc[exit_i])
        minimum = float(frame.low.iloc[entry_i + 1:exit_i + 1].min())
        rows.append({"entry_date": frame.index[entry_i], "exit_date": frame.index[exit_i],
                     "entry_i": int(entry_i), "hold": hold, "gross_return": exit_ / entry - 1,
                     "mae": minimum / entry - 1})
        last_exit = exit_i
    return pd.DataFrame(rows, columns=("entry_date", "exit_date", "entry_i", "hold",
                                       "gross_return", "mae"))


def net_returns(table: pd.DataFrame, bps: float, rollover: float) -> pd.Series:
    if table.empty:
        return pd.Series(dtype=float)
    elapsed = (table.exit_date - table.entry_date).dt.days.clip(lower=1)
    return table.gross_return - bps / 10000 - rollover * elapsed / 365.25


def metrics(values: pd.Series, dates: pd.Series | None = None) -> dict:
    values = values.astype(float)
    if values.empty:
        return {"trades": 0, "total_pct": 0, "profit_factor": 0, "max_drawdown_pct": 0,
                "positive_year_ratio": 0, "expectancy_bps": 0}
    curve = (1 + values).cumprod()
    drawdown = curve / curve.cummax() - 1
    wins, losses = values[values > 0].sum(), values[values < 0].sum()
    yearly = pd.DataFrame({"r": values.to_numpy(), "date": pd.to_datetime(dates).to_numpy()})
    annual = yearly.groupby(yearly.date.dt.year).r.apply(lambda x: (1 + x).prod() - 1)
    return {"trades": int(len(values)), "total_pct": float((curve.iloc[-1] - 1) * 100),
            "profit_factor": float(wins / abs(losses)) if losses < 0 else 99.0,
            "max_drawdown_pct": float(-drawdown.min() * 100),
            "positive_year_ratio": float((annual > 0).mean()),
            "expectancy_bps": float(values.mean() * 10000)}


def subset(table: pd.DataFrame, split: str) -> pd.DataFrame:
    start, end = SPLITS[split]
    return table[(table.entry_date >= start) & (table.entry_date <= end)].copy()


def evaluate(table: pd.DataFrame, split: str) -> dict:
    sample = subset(table, split)
    scenarios = {}
    for name, bps, carry in (("base", 8, .04), ("conservative", 15, .08), ("stress", 30, .12)):
        scenarios[name] = metrics(net_returns(sample, bps, carry), sample.entry_date)
    scenarios["worst_mae_pct"] = float(sample.mae.min() * 100) if not sample.empty else None
    return scenarios


def random_p(frame: pd.DataFrame, observed: pd.DataFrame, split: str, seed: int, runs: int = 1000) -> float:
    sample = subset(observed, split)
    if sample.empty:
        return 1.0
    start, end = SPLITS[split]
    eligible = np.flatnonzero((frame.index >= start) & (frame.index <= end))
    hold = int(sample["hold"].iloc[0])
    eligible = eligible[eligible + hold < len(frame)]
    observed_mean = float(net_returns(sample, 15, .08).mean())
    rng = np.random.default_rng(seed)
    superior = 0
    for _ in range(runs):
        chosen = rng.choice(eligible, size=len(sample), replace=len(eligible) < len(sample))
        gross = frame.close.iloc[chosen + hold].to_numpy() / frame.close.iloc[chosen].to_numpy() - 1
        days = (frame.index[chosen + hold] - frame.index[chosen]).days
        simulated = gross - .0015 - .08 * np.maximum(days, 1) / 365.25
        superior += float(np.mean(simulated)) >= observed_mean
    return (superior + 1) / (runs + 1)


def train_score(table: pd.DataFrame) -> float:
    sample = subset(table, "train")
    m = metrics(net_returns(sample, 15, .08), sample.entry_date)
    if m["trades"] < 20:
        return -math.inf
    penalty = max(0.0, m["max_drawdown_pct"] - 15) / 10
    return m["profit_factor"] * math.sqrt(m["trades"]) - penalty


def period_pass(result: dict) -> bool:
    return (result["base"]["trades"] >= 8 and result["base"]["profit_factor"] >= 1.2
            and result["stress"]["profit_factor"] >= 1.05
            and result["base"]["max_drawdown_pct"] <= 20
            and result["base"]["positive_year_ratio"] >= .6)


def run() -> dict:
    finalists = []
    for asset_i, asset in enumerate(ASSETS):
        frame = download(asset)
        candidates = [(train_score(table := trades(frame, params)), params, table) for params in GRID]
        score, params, table = max(candidates, key=lambda row: row[0])
        periods = {name: evaluate(table, name) for name in ("train", "validation", "oos")}
        p_values = {name: random_p(frame, table, name, 20260802 + asset_i * 10 + i)
                    for i, name in enumerate(("validation", "oos"))}
        passed = (period_pass(periods["validation"]) and period_pass(periods["oos"])
                  and all(p <= 1 / 60 for p in p_values.values()))
        finalists.append({"asset": asset, "parameters": {"drop_z": params[0],
                          "recovery_fraction": params[1], "holding_days": params[2],
                          "regime_sma200": params[3]}, "train_score": score,
                          "periods": periods, "random_empirical_p": p_values,
                          "passes_pre_holdout": passed})
    passing = [row for row in finalists if row["passes_pre_holdout"]]
    decision = "OPEN_SINGLE_FINALIST_HOLDOUT" if len(passing) == 1 else (
        "BLOCK_MULTIPLE_FINALISTS" if len(passing) > 1 else "REJECT_HOLDOUT_REMAINS_SEALED")
    return {"schema_version": 1, "methodology": "methodology_confirmed_capitulation_v1.json",
            "grid_variants_per_asset": len(GRID), "finalists": finalists,
            "holdout_evaluated": False, "decision": decision,
            "note": "Historical high/low contributes only to MAE audit; signals are close-only."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT / "confirmed_capitulation_v1_decision.json")
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
