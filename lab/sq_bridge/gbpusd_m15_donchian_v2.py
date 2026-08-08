#!/usr/bin/env python3
"""Preregistered low-turnover GBPUSD M15 Donchian trend screen."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.gbpusd_m15_v1 import SPLITS, load_m15


def prepare(frame: pd.DataFrame, channel: int) -> pd.DataFrame:
    data = frame.copy()
    previous = data.c.shift()
    true_range = pd.concat((data.h - data.l, (data.h - previous).abs(),
                            (data.l - previous).abs()), axis=1).max(axis=1)
    data["atr"] = true_range.rolling(96).mean()
    data["ema"] = data.c.ewm(span=192, adjust=False).mean()
    data["entry_high"] = data.h.shift().rolling(channel).max()
    data["entry_low"] = data.l.shift().rolling(channel).min()
    exit_channel = channel // 2
    data["exit_high"] = data.h.shift().rolling(exit_channel).max()
    data["exit_low"] = data.l.shift().rolling(exit_channel).min()
    return data


def simulate(frame: pd.DataFrame, channel: int, atr_multiple: float, side: int,
             maximum_hold: int = 960, minimum_hold: int = 0) -> pd.DataFrame:
    data = prepare(frame, channel)
    index = data.index
    open_ = data.o.to_numpy()
    high = data.h.to_numpy()
    low = data.l.to_numpy()
    close = data.c.to_numpy()
    atr = data.atr.to_numpy()
    ema = data.ema.to_numpy()
    entry_high = data.entry_high.to_numpy()
    entry_low = data.entry_low.to_numpy()
    exit_high = data.exit_high.to_numpy()
    exit_low = data.exit_low.to_numpy()
    rows = []
    i = max(channel, 192)
    while i < len(data) - 1:
        breakout = close[i] > entry_high[i] and close[i] > ema[i] if side == 1 else close[i] < entry_low[i] and close[i] < ema[i]
        if not breakout or not np.isfinite(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        entry_index = i + 1
        entry = float(open_[entry_index])
        distance = float(atr[i] * atr_multiple)
        stop = entry - side * distance
        exit_price = float(close[entry_index])
        exit_index = entry_index
        pending_channel_exit = False
        end = min(entry_index + maximum_hold - 1, len(data) - 1)
        for j in range(entry_index, end + 1):
            if pending_channel_exit:
                exit_price, exit_index = float(open_[j]), j
                break
            stopped = low[j] <= stop if side == 1 else high[j] >= stop
            if stopped:
                exit_price, exit_index = stop, j
                break
            can_exit = j - entry_index + 1 >= minimum_hold
            channel_exit = can_exit and (close[j] < exit_low[j] if side == 1 else close[j] > exit_high[j])
            if channel_exit and j < end:
                pending_channel_exit = True
            exit_price, exit_index = float(close[j]), j
        gross = side * (exit_price - entry) / entry
        rows.append({"date": index[entry_index], "exit_date": index[exit_index],
                     "gross": gross, "stop": distance / entry,
                     "bars": exit_index - entry_index + 1})
        i = exit_index + 1
    return pd.DataFrame(rows, columns=("date", "exit_date", "gross", "stop", "bars"))


def segment(trades: pd.DataFrame, name: str) -> pd.DataFrame:
    start, end = SPLITS[name]
    return trades[(trades.date >= start) & (trades.date <= end)]


def metrics(trades: pd.DataFrame, cost_bps: float) -> dict:
    if trades.empty:
        return {"n": 0, "pf": 0, "ev_usdc": -99, "dd_pct": 100,
                "positive_year_ratio": 0, "median_hours": None, "max_leverage": 0}
    stop = trades.stop.clip(lower=.0001)
    notional = np.minimum(2 / stop, 200 * 20)
    pnl = trades.gross * notional - cost_bps / 10_000 * notional
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = 200 + pnl.cumsum()
    drawdown = (1 - equity / equity.cummax()).max() * 100
    years = pd.Series(pnl.to_numpy(), index=pd.DatetimeIndex(trades.date)).groupby(lambda ts: ts.year).sum()
    return {
        "n": len(trades), "pf": float(wins / losses) if losses else 99,
        "ev_usdc": float(pnl.mean()), "net_usdc": float(pnl.sum()),
        "dd_pct": float(drawdown), "positive_year_ratio": float((years > 0).mean()),
        "median_hours": float(trades.bars.median() / 4),
        "max_leverage": float((notional / 200).max()),
    }


def passes(periods: dict) -> bool:
    validation, oos = periods["validation"], periods["oos"]
    return (
        validation["base"]["n"] >= 35 and oos["base"]["n"] >= 35
        and validation["base"]["pf"] >= 1.2 and oos["base"]["pf"] >= 1.2
        and validation["stress"]["pf"] >= 1.05 and oos["stress"]["pf"] >= 1.05
        and validation["stress"]["ev_usdc"] >= .1 and oos["stress"]["ev_usdc"] >= .1
        and validation["base"]["positive_year_ratio"] >= .6
        and oos["base"]["positive_year_ratio"] >= .6
        and validation["base"]["dd_pct"] <= 25 and oos["base"]["dd_pct"] <= 25
    )


def run(path: Path) -> dict:
    data = load_m15(path)
    families = []
    for side, name in ((1, "donchian_trend_long"), (-1, "donchian_trend_short")):
        variants = []
        for channel in (96, 192, 384):
            for atr_multiple in (2.0, 3.0):
                candidate = simulate(data, channel, atr_multiple, side)
                train = metrics(segment(candidate, "train"), 15)
                score = train["pf"] * math.sqrt(train["n"]) if train["n"] >= 35 and train["ev_usdc"] > 0 else -1
                variants.append((score, channel, atr_multiple, candidate, train))
        _, channel, atr_multiple, selected, train = max(variants, key=lambda item: item[0])
        periods = {
            split: {scenario: metrics(segment(selected, split), cost)
                    for scenario, cost in (("base", 8), ("conservative", 15), ("stress", 30))}
            for split in SPLITS
        }
        families.append({"family": name, "selected_on_train": {"channel": channel, "atr_multiple": atr_multiple},
                         "train_selection_metric_at_15bps": train, "periods": periods,
                         "passes_pre_holdout": passes(periods)})
    eligible = [item["family"] for item in families if item["passes_pre_holdout"]]
    return {"methodology": "methodology_gbpusd_m15_donchian_v2.json", "source": str(path),
            "attempted_variants": 12, "holdout_evaluated": False, "families": families,
            "eligible": eligible, "decision": "PASS_TO_SQCLI" if eligible else "REJECT_NO_SQCLI"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
