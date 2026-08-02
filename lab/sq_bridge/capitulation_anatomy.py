#!/usr/bin/env python3
"""Anatomy and falsification audit of the frozen capitulation_d1 setup."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from packages.portfolio.risk_policy import parse_risk_glidepath, risk_pct_for_capital

OUT = ROOT / "lab" / "out" / "alquimia" / "capitulation_anatomy_v1.json"
ASSETS = ("MSFT", "NVDA", "QQQ")
LEVERAGES = (1, 2, 3, 5, 8, 10, 15, 20, 30, 50)
STOP_DISTANCE = {"MSFT": .0476, "NVDA": .0700, "QQQ": .0522}
DEFAULT_GLIDEPATH = parse_risk_glidepath(
    "400:.015,1000:.0125,2500:.01,5000:.0075,inf:.005"
)


def download(asset: str) -> pd.DataFrame:
    import yfinance as yf

    frame = yf.download(asset, start="2003-01-01", end="2026-08-02", auto_adjust=True,
                        actions=False, progress=False)
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    return frame[["open", "high", "low", "close"]].dropna().astype(float)


def event_table(frame: pd.DataFrame) -> pd.DataFrame:
    close, open_ = frame.close, frame.open
    mean = close.rolling(20).mean()
    lower = mean - 2 * close.rolling(20).std(ddof=0)
    body = close / open_ - 1
    signal = (body < -.02) & (close < lower)
    daily_vol = close.pct_change().rolling(20).std(ddof=0).shift(1)
    vol_median = daily_vol.expanding(min_periods=252).median()
    rows = []
    for signal_i in np.flatnonzero(signal.to_numpy()):
        entry_i = signal_i + 1
        if entry_i + 5 >= len(frame):
            continue
        entry = float(open_.iloc[entry_i])
        item = {"signal_date": frame.index[signal_i], "entry_date": frame.index[entry_i],
                "signal_close": float(close.iloc[signal_i]), "entry_open": entry,
                "overnight_gap": entry / float(close.iloc[signal_i]) - 1,
                "above_sma200": bool(close.iloc[signal_i] > close.rolling(200).mean().iloc[signal_i]),
                "high_vol": bool(daily_vol.iloc[signal_i] > vol_median.iloc[signal_i]),
                "era": "2020_plus" if frame.index[signal_i].year >= 2020 else "pre_2020"}
        for hold in (1, 2, 3, 5):
            end_i = entry_i + hold - 1
            item[f"return_{hold}d"] = float(close.iloc[end_i] / entry - 1)
            item[f"mae_{hold}d"] = float(frame.low.iloc[entry_i:end_i + 1].min() / entry - 1)
            item[f"mfe_{hold}d"] = float(frame.high.iloc[entry_i:end_i + 1].max() / entry - 1)
        rows.append(item)
    return pd.DataFrame(rows)


def trade_metrics(values: pd.Series, cost_bps: float = 0) -> dict:
    net = values.dropna().astype(float) - cost_bps / 10000
    if net.empty:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "expectancy_bps": 0,
                "total_pct": 0, "max_drawdown_pct": 0}
    wins, losses = net[net > 0].sum(), net[net < 0].sum()
    curve = (1 + net).cumprod()
    dd = curve / curve.cummax() - 1
    return {"trades": int(len(net)), "win_rate": float((net > 0).mean()),
            "profit_factor": float(wins / abs(losses)) if losses < 0 else 99.0,
            "expectancy_bps": float(net.mean() * 10000),
            "total_pct": float((curve.iloc[-1] - 1) * 100),
            "max_drawdown_pct": float(-dd.min() * 100)}


def bootstrap_mean_ci(values: pd.Series, rng: np.random.Generator, runs: int = 5000) -> list[float]:
    clean = values.dropna().to_numpy(float)
    if len(clean) == 0:
        return [0.0, 0.0]
    means = np.mean(rng.choice(clean, size=(runs, len(clean)), replace=True), axis=1)
    return [float(x * 10000) for x in np.quantile(means, [.025, .975])]


def random_entry_p(frame: pd.DataFrame, events: pd.DataFrame, rng: np.random.Generator,
                   runs: int = 5000) -> float:
    """Compare canonical intraday mean to random entry days matched by calendar year."""
    observed = float(events.return_1d.mean())
    candidates: dict[int, np.ndarray] = {}
    intraday = frame.close / frame.open - 1
    for year in events.entry_date.dt.year.unique():
        candidates[int(year)] = intraday[frame.index.year == year].dropna().to_numpy(float)
    superior = 0
    event_years = events.entry_date.dt.year.to_numpy()
    for _ in range(runs):
        sample = np.array([rng.choice(candidates[int(year)]) for year in event_years])
        superior += float(sample.mean()) >= observed
    return float((superior + 1) / (runs + 1))


def leverage_audit(events: pd.DataFrame) -> dict:
    worst = float(-events.mae_1d.min())
    buffered = worst * 1.25
    safe = [lev for lev in LEVERAGES if buffered < 1 / lev]
    cap = max(safe) if safe else None
    adverse = -events.mae_1d
    stop_distance = max(float(adverse.quantile(.95)) * 1.25, .005)
    risk_usdc = 2.0
    notional = risk_usdc / stop_distance
    margin_limited_notional = 200 * .35 * cap if cap else 0
    worst_row = events.loc[events.mae_1d.idxmin()]
    return {"worst_observed_mae_pct": worst * 100, "buffered_mae_pct": buffered * 100,
            "worst_mae_entry_date": str(worst_row.entry_date.date()),
            "maximum_grid_leverage_below_buffered_barrier": cap,
            "observed_liquidation_rate_by_leverage": {
                str(lev): float((adverse >= 1 / lev).mean()) for lev in LEVERAGES},
            "diagnostic_stop_distance_pct": stop_distance * 100,
            "risk_limited_notional_usdc": notional,
            "margin_limited_notional_usdc_at_cap": margin_limited_notional,
            "deployable_notional_usdc": min(notional, margin_limited_notional),
            "warning": "Historical Yahoo low proxy; requires native Ostium OHLC/gap certification."}


def analyse(asset: str, frame: pd.DataFrame, seed: int) -> dict:
    events = event_table(frame)
    rng = np.random.default_rng(seed)
    canonical = {name: trade_metrics(events.return_1d, bps) for name, bps in
                 (("gross", 0), ("base", 8), ("conservative", 15), ("stress", 30))}
    horizons = {str(hold): trade_metrics(events[f"return_{hold}d"], 15)
                for hold in (1, 2, 3, 5)}
    regimes = {}
    for column in ("above_sma200", "high_vol", "era"):
        regimes[column] = {str(value): trade_metrics(group.return_1d, 15)
                           for value, group in events.groupby(column)}
    years = {str(year): trade_metrics(group.return_1d, 15)
             for year, group in events.groupby(events.entry_date.dt.year)}
    stop = STOP_DISTANCE[asset]
    stopped_returns = events.return_1d.where(events.mae_1d > -stop, -stop)
    risk_notional = 200 * .01 / stop
    stopped_economics = {}
    for name, bps in (("base", 8), ("conservative", 15), ("stress", 30)):
        stopped_net = stopped_returns - bps / 10000
        stopped_economics[name] = trade_metrics(stopped_returns, bps) | {
            "expectancy_usdc": float(stopped_net.mean() * risk_notional),
            "total_pnl_usdc_fixed_notional": float(stopped_net.sum() * risk_notional),
        }
    stopped_economics["stop_distance_pct"] = stop * 100
    stopped_economics["risk_budget_usdc"] = 2.0
    stopped_economics["notional_usdc"] = risk_notional
    stopped_economics["stop_trigger_rate"] = float((events.mae_1d <= -stop).mean())
    temporal = {}
    for name, start, end in (("2003_2013", "2003-01-01", "2013-12-31"),
                             ("2014_2018", "2014-01-01", "2018-12-31"),
                             ("2019_2023", "2019-01-01", "2023-12-31"),
                             ("2024_2026_monitoring", "2024-01-01", "2026-08-01")):
        sample = events[(events.entry_date >= start) & (events.entry_date <= end)]
        temporal[name] = trade_metrics(sample.return_1d, 15)
    return {"asset": asset, "first_signal": str(events.signal_date.min().date()),
            "last_signal": str(events.signal_date.max().date()), "canonical_1d": canonical,
            "overnight_gap_bps_mean": float(events.overnight_gap.mean() * 10000),
            "overnight_gap_bps_median": float(events.overnight_gap.median() * 10000),
            "canonical_expectancy_bootstrap_95_ci_bps": bootstrap_mean_ci(events.return_1d - .0015, rng),
            "random_year_matched_empirical_p": random_entry_p(frame, events, rng),
            "diagnostic_horizons_conservative": horizons, "regimes_conservative": regimes,
            "temporal_conservative": temporal, "years_conservative": years,
            "stopped_small_account_200_usdc": stopped_economics,
            "risk_and_leverage": leverage_audit(events)}


def simulate_portfolio_glidepath(frames: dict[str, pd.DataFrame]) -> dict:
    rows = []
    for asset in ("MSFT", "NVDA"):
        events = event_table(frames[asset])
        stop = STOP_DISTANCE[asset]
        stopped = events.return_1d.where(events.mae_1d > -stop, -stop)
        rows.extend((date, float(value), stop) for date, value in zip(events.entry_date, stopped))
    scenarios = {}
    for name, bps in (("base", 8), ("conservative", 15), ("stress", 30)):
        by_date = {}
        for date, value, stop in rows:
            by_date.setdefault(date, []).append((value - bps / 10000, stop))
        capital = peak = 200.0
        max_drawdown = 0.0
        reached = {}
        for date, trades_on_day in sorted(by_date.items()):
            risk_pct = risk_pct_for_capital(capital, DEFAULT_GLIDEPATH, .01)
            capital *= 1 + sum(net * risk_pct / stop for net, stop in trades_on_day)
            peak = max(peak, capital)
            max_drawdown = max(max_drawdown, 1 - capital / peak)
            for threshold in (400, 1000, 2500, 5000):
                if capital >= threshold and str(threshold) not in reached:
                    reached[str(threshold)] = str(date.date())
        scenarios[name] = {"initial_usdc": 200.0, "final_usdc": capital,
                           "profit_usdc": capital - 200, "total_return_pct": (capital / 200 - 1) * 100,
                           "maximum_drawdown_pct": max_drawdown * 100,
                           "capital_threshold_dates": reached}
    return {"assets": ["MSFT", "NVDA"], "trades": len(rows),
            "simultaneous_signals_use_same_start_of_day_capital": True,
            "tiers": [{"capital_below": "inf" if math.isinf(tier.capital_below) else tier.capital_below,
                       "risk_pct": tier.risk_pct}
                      for tier in DEFAULT_GLIDEPATH], "scenarios": scenarios}


def run() -> dict:
    frames = {asset: download(asset) for asset in ASSETS}
    assets = [analyse(asset, frames[asset], 20260802 + i) for i, asset in enumerate(ASSETS)]
    return {"schema_version": 1, "methodology": "methodology_capitulation_anatomy_v1.json",
            "production_rule_changed": False, "assets": assets,
            "portfolio_risk_glidepath": simulate_portfolio_glidepath(frames),
            "decision": "DESCRIPTIVE_AUDIT_ONLY_KEEP_PAPER_RULE_FROZEN"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
