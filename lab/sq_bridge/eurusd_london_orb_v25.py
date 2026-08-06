#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

import pandas as pd


def load_m15(root: Path) -> pd.DataFrame:
    import duckdb

    pattern = str(root / "EURUSD" / "tf=1m" / "year=*" / "month=*" / "data.parquet")
    query = f"""SELECT time_bucket(INTERVAL '15 minutes', to_timestamp(ts)) t,
      arg_min(open,ts) o,max(high) h,min(low) l,arg_max(close,ts) c,count(*) n
      FROM read_parquet('{pattern}') GROUP BY t ORDER BY t"""
    frame = duckdb.sql(query).df()
    frame.index = pd.to_datetime(frame.pop("t"), utc=True)
    return frame[(frame.n >= 10) & (frame.c > 0) & (frame.h > frame.l)]


def variants(config: dict):
    search = config["search"]
    yield from itertools.product(search["range_minutes"], search["buffer_range_fraction"],
                                 search["stop_range_fraction"], search["reward_risk"], search["side"])


_DAY_CACHE: dict[int, list[pd.DataFrame]] = {}


def session_days(frame: pd.DataFrame) -> list[pd.DataFrame]:
    key = id(frame)
    if key not in _DAY_CACHE:
        local = frame.index.tz_convert("Europe/London")
        dates = pd.Series(local.date, index=frame.index)
        _DAY_CACHE[key] = [frame.loc[indices] for indices in dates.groupby(dates, sort=False).groups.values()]
    return _DAY_CACHE[key]


def simulate(frame: pd.DataFrame, variant: tuple) -> pd.DataFrame:
    range_minutes, buffer_fraction, stop_fraction, reward_risk, side_name = variant
    side = 1 if side_name == "long" else -1
    rows = []
    range_bars = range_minutes // 15
    for day in session_days(frame):
        hours = day.index.tz_convert("Europe/London")
        early = day[(hours.hour >= 7) & (hours.hour < 9)].iloc[:range_bars]
        if len(early) != range_bars:
            continue
        high, low = float(early.h.max()), float(early.l.min())
        width = high - low
        if width <= 0:
            continue
        search = day[(hours.hour >= 8) & (hours.hour < 11)]
        level = high + buffer_fraction * width if side == 1 else low - buffer_fraction * width
        hits = search.index[search.c > level] if side == 1 else search.index[search.c < level]
        if len(hits) == 0:
            continue
        signal_pos = frame.index.get_loc(hits[0])
        if signal_pos + 1 >= len(frame):
            continue
        entry_time = frame.index[signal_pos + 1]
        if entry_time.date() != hits[0].date():
            continue
        entry = float(frame.iloc[signal_pos + 1].o)
        distance = width * stop_fraction
        stop, target = entry - side * distance, entry + side * distance * reward_risk
        exit_window = day[(day.index >= entry_time) & (hours.hour < 16)]
        if exit_window.empty:
            continue
        exit_price, exit_time = float(exit_window.iloc[-1].c), exit_window.index[-1]
        for bar in exit_window.itertuples():
            hit_stop = bar.l <= stop if side == 1 else bar.h >= stop
            hit_target = bar.h >= target if side == 1 else bar.l <= target
            if hit_stop or hit_target:
                exit_price, exit_time = (stop if hit_stop else target), bar.Index
                break
        rows.append({"date": entry_time, "exit": exit_time, "gross_return": side * (exit_price-entry)/entry,
                     "stop_fraction": distance/entry})
    return pd.DataFrame(rows)


def metrics(trades: pd.DataFrame, bps: float, economics: dict) -> dict:
    if trades.empty:
        return {"trades": 0, "profit_factor": 0, "expectancy_usdc": -99,
                "max_drawdown_pct": 100, "positive_year_ratio": 0}
    risk = economics["capital_usdc"] * economics["risk_per_trade_pct"] / 100
    notional = risk / trades.stop_fraction.clip(lower=.0005)
    pnl = notional * (trades.gross_return - bps/10000) - economics["opening_oracle_usdc"]
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    equity = economics["capital_usdc"] + pnl.cumsum()
    drawdown = (1 - equity/equity.cummax()).max()
    years = pd.Series(pnl.values, index=pd.DatetimeIndex(trades.date)).groupby(lambda x: x.year).sum()
    return {"trades": len(pnl), "profit_factor": float(gains/losses) if losses else 99,
            "expectancy_usdc": float(pnl.mean()), "net_pnl_usdc": float(pnl.sum()),
            "max_drawdown_pct": float(drawdown*100), "positive_year_ratio": float((years > 0).mean())}


def passes(m: dict, minimum_trades: int, gates: dict) -> bool:
    return (m["trades"] >= minimum_trades and m["profit_factor"] >= gates["minimum_base_profit_factor"]
            and m["max_drawdown_pct"] <= gates["maximum_drawdown_pct"]
            and m["positive_year_ratio"] >= gates["minimum_positive_year_ratio"])


def run(root: Path, config: dict) -> dict:
    frame = load_m15(root).loc[config["splits"]["train"][0]:config["splits"]["oos"][1]]
    costs, gates, economics = config["economics"]["roundtrip_bps"], config["gates"], config["economics"]
    evaluated = []
    for variant in variants(config):
        all_trades = simulate(frame, variant)
        periods = {}
        for name in ("train", "validation", "oos"):
            start, end = config["splits"][name]
            sample = all_trades[(all_trades.date >= start) & (all_trades.date <= end)]
            periods[name] = {scenario: metrics(sample, bps, economics) for scenario, bps in costs.items()}
        train_ok = passes(periods["train"]["base"], gates["train_minimum_trades"], gates)
        train_stress = periods["train"]["stress"]
        train_ok &= (train_stress["profit_factor"] >= gates["minimum_stress_profit_factor"]
                     and train_stress["expectancy_usdc"] >= gates["minimum_stress_expectancy_usdc"])
        evaluated.append({"variant": variant, "train_pass": train_ok, "periods": periods})
    eligible = [row for row in evaluated if row["train_pass"]]
    finalist = max(eligible, key=lambda row: row["periods"]["train"]["stress"]["expectancy_usdc"], default=None)
    final_pass = False
    if finalist:
        final_pass = all(
            passes(finalist["periods"][name]["base"], gates[f"{name}_minimum_trades"], gates)
            and finalist["periods"][name]["stress"]["profit_factor"] >= gates["minimum_stress_profit_factor"]
            and finalist["periods"][name]["stress"]["expectancy_usdc"] >= gates["minimum_stress_expectancy_usdc"]
            for name in ("validation", "oos")
        )
    return {"methodology": config["methodology_id"], "data": {"first": str(frame.index.min()),
            "last": str(frame.index.max()), "bars": len(frame)}, "variants_attempted": len(evaluated),
            "train_eligible": len(eligible), "finalist": finalist, "holdout_evaluated": False,
            "decision": "PASS_TO_SQCLI" if final_pass else "REJECT_NO_SQCLI"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--methodology", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.methodology.read_bytes()
    config = json.loads(raw)
    result = run(args.root, config)
    result["methodology_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"decision": result["decision"], "variants_attempted": result["variants_attempted"],
                      "train_eligible": result["train_eligible"], "finalist": result["finalist"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
