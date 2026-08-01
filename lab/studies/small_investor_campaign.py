"""Reproducible small-investor strategy campaign.

Signals are computed at the close and positions are applied from the next
session's open. Parameters are selected on development data only. Validation
and final test are reported separately. This is research, not live execution.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "lab" / "out" / "small_investor_campaign"
OUT.mkdir(parents=True, exist_ok=True)

ASSETS = ("SPY", "QQQ", "IWM", "GLD", "TLT")
START, END = "2004-01-01", "2026-08-01"
DEV_END, VAL_END = "2017-12-31", "2022-12-31"
LEVERAGES = (1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0)
ROUND_TRIP_COST = 0.0010       # conservative ETF/perp proxy cost
FINANCING_ANNUAL = 0.06        # cost on borrowed exposure only


def download() -> dict[str, pd.DataFrame]:
    data = {}
    for symbol in ASSETS:
        frame = yf.download(symbol, start=START, end=END, auto_adjust=True,
                            progress=False, actions=False)
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        frame = frame.rename(columns={"Open": "O", "High": "H", "Low": "L", "Close": "C"})
        data[symbol] = frame[["O", "H", "L", "C"]].dropna().astype(float)
    return data


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def hold_rules(entry: pd.Series, exit_: pd.Series, max_hold: int) -> pd.Series:
    pos = pd.Series(0.0, index=entry.index)
    active, age = False, 0
    for i in range(len(pos)):
        if active and (bool(exit_.iloc[i]) or age >= max_hold):
            active, age = False, 0
        if not active and bool(entry.iloc[i]):
            active, age = True, 0
        pos.iloc[i] = float(active)
        if active:
            age += 1
    return pos


def signal(family: str, df: pd.DataFrame, p: tuple) -> pd.Series:
    c, o = df.C, df.O
    if family == "mean_reversion":
        threshold, max_hold = p
        rr = rsi(c, 2)
        return hold_rules((c > c.rolling(200).mean()) & (rr < threshold), rr > 60, max_hold)
    if family == "capitulation_confirmed":
        drop, max_hold = p
        lower = c.rolling(20).mean() - 2 * c.rolling(20).std(ddof=0)
        capit = ((c - o) / o < -drop) & (c < lower)
        confirm = capit.shift(1).fillna(False) & (c > c.shift(1))
        return hold_rules(confirm, c > c.rolling(5).mean(), max_hold)
    if family == "trend_pullback":
        threshold, max_hold = p
        rr = rsi(c, 5)
        trend = c > c.rolling(200).mean()
        return hold_rules(trend & (c < c.rolling(20).mean()) & (rr < threshold),
                          c > c.rolling(20).mean(), max_hold)
    if family == "donchian_breakout":
        entry_n, exit_n = p
        return hold_rules(c > df.H.rolling(entry_n).max().shift(1),
                          c < df.L.rolling(exit_n).min().shift(1), 400)
    if family == "time_series_trend":
        fast, slow = p
        return (c.rolling(fast).mean() > c.rolling(slow).mean()).astype(float)
    if family == "short_term_reversal":
        drop, max_hold = p
        trend = c > c.rolling(200).mean()
        return hold_rules(trend & (c.pct_change(3) < -drop), c > c.rolling(5).mean(), max_hold)
    raise ValueError(family)


def returns(df: pd.DataFrame, close_signal: pd.Series, leverage: float = 1.0,
            cost_mult: float = 1.0) -> pd.Series:
    # Close signal t becomes exposure from open(t+1) to open(t+2).
    exposure = close_signal.shift(1).fillna(0.0)
    open_ret = df.O.shift(-1) / df.O - 1
    turnover = exposure.diff().abs().fillna(exposure.abs())
    trading = turnover * ROUND_TRIP_COST * 0.5 * leverage * cost_mult
    financing = exposure * max(leverage - 1.0, 0.0) * FINANCING_ANNUAL / 252
    out = exposure * open_ret.fillna(0.0) * leverage - trading - financing
    if leverage > 1.0:
        # Conservative barrier while exposed from today open to next open.
        worst_price = pd.concat([df.L, df.O.shift(-1)], axis=1).min(axis=1)
        adverse = worst_price / df.O - 1
        liquidated = (exposure > 0) & (adverse <= -(1.0 / leverage))
        out.loc[liquidated] = -1.0
    return out.iloc[:-1]


def metrics(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if ret.empty:
        return {"cagr": -1, "sharpe": -99, "max_dd": 1, "pf": 0, "total": -1, "months_p5": -1}
    equity = (1 + ret).cumprod()
    years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1 / 252)
    cagr = equity.iloc[-1] ** (1 / years) - 1 if equity.iloc[-1] > 0 else -1
    vol = ret.std() * np.sqrt(252)
    sharpe = ret.mean() * 252 / vol if vol > 0 else 0
    dd = equity / equity.cummax() - 1
    wins, losses = ret[ret > 0].sum(), ret[ret < 0].sum()
    monthly = (1 + ret).resample("ME").prod() - 1
    return {"cagr": float(cagr), "sharpe": float(sharpe), "max_dd": float(-dd.min()),
            "pf": float(wins / abs(losses)) if losses else 99.0,
            "total": float(equity.iloc[-1] - 1), "months_p5": float(monthly.quantile(.05)),
            "positive_years": float(((1 + ret).resample("YE").prod() - 1 > 0).mean())}


def segment(ret: pd.Series, name: str) -> pd.Series:
    if name == "dev": return ret.loc[:DEV_END]
    if name == "validation": return ret.loc["2018-01-01":VAL_END]
    return ret.loc["2023-01-01":]


GRIDS = {
    "mean_reversion": [(x, h) for x in (5, 10, 15) for h in (3, 5, 7)],
    "capitulation_confirmed": [(x, h) for x in (.015, .02, .025) for h in (2, 3, 5)],
    "trend_pullback": [(x, h) for x in (25, 30, 35) for h in (5, 8, 12)],
    "donchian_breakout": [(e, x) for e in (40, 60, 100) for x in (10, 20, 40) if x < e],
    "time_series_trend": [(f, s) for f in (20, 50, 100) for s in (100, 150, 200) if f < s],
    "short_term_reversal": [(d, h) for d in (.02, .03, .04) for h in (3, 5, 8)],
}

FAMILY_ASSETS = {
    "mean_reversion": ("SPY", "QQQ", "IWM"),
    "capitulation_confirmed": ("SPY", "QQQ", "IWM"),
    "trend_pullback": ("SPY", "QQQ", "IWM"),
    "donchian_breakout": ("SPY", "QQQ", "GLD", "TLT"),
    "time_series_trend": ("SPY", "QQQ", "GLD", "TLT"),
    "short_term_reversal": ("SPY", "QQQ", "IWM"),
}


def choose_variants(data: dict[str, pd.DataFrame]) -> list[dict]:
    selected = []
    for family, assets in FAMILY_ASSETS.items():
        scored = []
        for asset, params in itertools.product(assets, GRIDS[family]):
            sig = signal(family, data[asset], params)
            ret = returns(data[asset], sig)
            m = metrics(segment(ret, "dev"))
            # Penalise drawdown; no validation/test information enters selection.
            score = m["sharpe"] + 0.5 * m["cagr"] - 1.5 * m["max_dd"]
            scored.append((score, asset, params, sig, ret, m))
        score, asset, params, sig, ret, dev = max(scored, key=lambda x: x[0])
        val, test = metrics(segment(ret, "validation")), metrics(segment(ret, "test"))
        neighbours = [x for x in scored if x[1] == asset]
        robust = np.mean([metrics(segment(x[4], "validation"))["total"] > 0 for x in neighbours])
        entries = sig.eq(1) & sig.shift(1).fillna(0).eq(0)
        samples = {"total": int(entries.sum()),
                   "validation": int(entries.loc["2018-01-01":VAL_END].sum()),
                   "test": int(entries.loc["2023-01-01":].sum())}
        selected.append({"family": family, "asset": asset, "params": params, "signal": sig,
                         "base_returns": ret, "dev": dev, "validation": val, "test": test,
                         "samples": samples,
                         "neighbour_positive_validation": float(robust)})
    return selected


def leverage_gate(item: dict, data: dict[str, pd.DataFrame]) -> tuple[float | None, list[dict]]:
    rows, chosen = [], None
    for lev in LEVERAGES:
        ret = returns(data[item["asset"]], item["signal"], lev)
        stressed = returns(data[item["asset"]], item["signal"], lev, 2.0)
        val, test = metrics(segment(ret, "validation")), metrics(segment(ret, "test"))
        sv, st = metrics(segment(stressed, "validation")), metrics(segment(stressed, "test"))
        selection_pass = (val["max_dd"] <= .20 and val["pf"] >= 1.20 and
                          val["months_p5"] >= -.10 and sv["total"] > 0)
        test_pass = (test["max_dd"] <= .25 and test["pf"] >= 1.20 and
                     test["months_p5"] >= -.10 and st["total"] > 0)
        rows.append({"leverage": lev, "selection_pass": selection_pass,
                     "test_pass": test_pass, "validation": val, "test": test,
                     "stress_validation": sv, "stress_test": st})
        if selection_pass:
            chosen = lev
    return chosen, rows


def main() -> None:
    data = download()
    selected = choose_variants(data)
    serial = []
    for item in selected:
        lev, sweep = leverage_gate(item, data)
        selected_row = next((row for row in sweep if row["leverage"] == lev), None)
        gate = (item["validation"]["pf"] >= 1.25 and item["test"]["pf"] >= 1.25 and
                item["validation"]["total"] > 0 and item["test"]["total"] > 0 and
                item["neighbour_positive_validation"] >= .70 and
                item["samples"]["total"] >= 40 and item["samples"]["validation"] >= 10 and
                item["samples"]["test"] >= 8 and lev is not None and
                selected_row is not None and selected_row["test_pass"])
        serial.append({k: v for k, v in item.items() if k not in ("signal", "base_returns")} |
                      {"selected_leverage": lev, "accepted": gate, "leverage_sweep": sweep})
    artifact = {"protocol": "SMALL_INVESTOR_RESEARCH_PROTOCOL.md", "data_end": END,
                "assets": ASSETS, "results": serial}
    (OUT / "results.json").write_text(json.dumps(artifact, indent=2, default=str))
    lines = ["# Small-investor campaign — results", "", "| Family | Asset | Params | Val PF | Test PF | Test CAGR | Test DD | Lev | Gate |",
             "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for r in serial:
        lines.append(f"| {r['family']} | {r['asset']} | `{r['params']}` | {r['validation']['pf']:.2f} | "
                     f"{r['test']['pf']:.2f} | {r['test']['cagr']:.1%} | {r['test']['max_dd']:.1%} | "
                     f"{r['selected_leverage'] or '-'} | {'ACCEPTED' if r['accepted'] else 'REJECTED'} |")
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
