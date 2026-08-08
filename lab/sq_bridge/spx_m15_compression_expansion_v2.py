#!/usr/bin/env python3
"""Development-only SPX M15 compression/expansion falsification screen."""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from spxusd_execution_economics import liquidation_distance_pct


def load_m15(path: Path) -> pd.DataFrame:
    import duckdb
    frame = duckdb.connect(":memory:").execute("""
      SELECT CAST(floor(ts/900)*900 AS BIGINT) ts, arg_min(open,ts) open,
        max(high) high, min(low) low, arg_max(close,ts) close_price, count(*) minute_count
      FROM read_parquet(?)
      WHERE year(to_timestamp(ts) AT TIME ZONE 'America/New_York') BETWEEN 2012 AND 2018
      GROUP BY 1 ORDER BY 1
    """, [str(path)]).fetchdf()
    frame = frame.rename(columns={"close_price": "close"})
    frame.index = pd.to_datetime(frame.ts, unit="s", utc=True)
    local = frame.index.tz_convert("America/New_York")
    frame["year"] = local.year
    frame["weekday"] = local.weekday
    frame["hour_ny"] = local.hour
    frame["complete"] = frame.minute_count >= 12
    previous = frame.close.shift(1)
    tr = pd.concat((frame.high-frame.low, (frame.high-previous).abs(), (frame.low-previous).abs()), axis=1).max(axis=1)
    frame["atr"] = tr.ewm(alpha=1/14, adjust=False, min_periods=28).mean()
    frame["natr"] = frame.atr/frame.close
    return frame


def leverage_plan(stop_distance: float, config: dict) -> dict | None:
    risk_fraction = config["risk_per_trade_pct"]/100
    exposure = risk_fraction/stop_distance
    for leverage in (50, 30, 20, 15, 10, 5, 3, 2, 1):
        if leverage > config["venue_max_leverage"] or exposure/leverage > config["maximum_margin_pct"]/100:
            continue
        if liquidation_distance_pct(leverage, config["venue_max_leverage"])/100 >= stop_distance*config["liquidation_buffer_over_stop"]:
            return {"leverage": leverage, "exposure": exposure, "margin": exposure/leverage}
    return None


def simulate(frame: pd.DataFrame, p: dict, account: dict, costs: dict) -> list[dict]:
    lookback, channel = p["compression_lookback_bars"], p["channel_bars"]
    rank = frame.natr.shift(1).rolling(lookback).rank(pct=True)
    compressed = rank <= p["compression_quantile"]
    upper = frame.high.shift(1).rolling(channel).max(); lower = frame.low.shift(1).rolling(channel).min()
    trigger = frame.close > upper if p["side"] == "long" else frame.close < lower
    day = pd.Series(True, index=frame.index)
    if p["day_filter"] == "no_monday": day &= frame.weekday != 0
    if p["day_filter"] == "no_friday": day &= frame.weekday != 4
    signal = compressed & trigger & day & (frame.hour_ny == p["signal_hour_ny"]) & frame.complete
    direction = 1 if p["side"] == "long" else -1
    o,h,l,c,atr,complete = (frame[x].to_numpy() for x in ("open","high","low","close","atr","complete"))
    years = frame.year.to_numpy(); trades=[]; last_exit=-1
    for at in np.flatnonzero(signal.to_numpy()):
        entry_i=at+1
        if entry_i>=len(frame) or entry_i<=last_exit or not complete[entry_i]: continue
        entry=float(o[entry_i]); stop_distance=p["stop_atr"]*float(atr[at])/entry
        plan=leverage_plan(stop_distance,account)
        if plan is None: continue
        stop=entry*(1-direction*stop_distance); exit_i=min(entry_i+p["hold_bars"]-1,len(frame)-1)
        exit_price=float(c[exit_i]); reason="time"; invalid=False
        for i in range(entry_i,exit_i+1):
            if not complete[i]: invalid=True; exit_i=i; break
            hit=l[i]<=stop if direction==1 else h[i]>=stop
            if hit:
                exit_i=i; exit_price=min(float(o[i]),stop) if direction==1 else max(float(o[i]),stop); reason="stop"; break
        last_exit=exit_i
        if invalid: continue
        gross=direction*(exit_price/entry-1)
        trade={"year":int(years[entry_i]),"gross":gross,"leverage":plan["leverage"],"margin":plan["margin"],"reason":reason}
        for name,bps in costs.items():
            trade[name]=plan["exposure"]*(gross-bps/10_000)-0.1/account["capital_usdc"]
        trades.append(trade)
    return trades


def metrics(trades: list[dict], scenario: str) -> dict:
    values=np.array([t[scenario] for t in trades]); equity=np.cumsum(values); peaks=np.maximum.accumulate(np.r_[0,equity])
    dd=float(np.max(peaks[1:]-equity)) if len(values) else 0
    gains=float(values[values>0].sum()); losses=float(-values[values<0].sum())
    yearly=pd.Series(values).groupby([t["year"] for t in trades]).sum() if trades else pd.Series(dtype=float)
    return {"trades":len(trades),"expectancy_usdc":round(float(values.mean()*200),6) if len(values) else None,
            "profit_factor":round(gains/losses,6) if losses else None,"net_pct":round(float(values.sum()*100),6),
            "drawdown_pct":round(dd*100,6),"positive_year_ratio":round(float((yearly>0).mean()),6) if len(yearly) else 0}


def grid(config: dict):
    keys=tuple(config["grid"])
    for values in itertools.product(*(config["grid"][k] for k in keys)): yield dict(zip(keys,values))


def run(parquet: Path, config: dict) -> dict:
    frame=load_m15(parquet); rows=[]; gate=config["development_gate"]
    for p in grid(config):
        trades=simulate(frame,p,config["small_account"],config["costs_bps"])
        measured={name:metrics(trades,name) for name in config["costs_bps"]}; stress=measured["stress"]
        passed=(stress["trades"]>=gate["minimum_trades"] and (stress["profit_factor"] or 0)>=gate["minimum_stress_profit_factor"]
                and stress["positive_year_ratio"]>=gate["minimum_positive_year_ratio"] and stress["drawdown_pct"]<=gate["maximum_stress_drawdown_pct"]
                and (stress["expectancy_usdc"] or -999)>=gate["minimum_stress_expectancy_usdc"])
        rows.append({"parameters":p,"metrics":measured,"passes":bool(passed)})
    passing=[r for r in rows if r["passes"]]
    return {"schema_version":1,"family":config["id"],"attempted":len(rows),"passes":len(passing),
            "top_20":sorted(rows,key=lambda r:(r["metrics"]["stress"]["profit_factor"] or 0),reverse=True)[:20],
            "passing":passing,"validation_accessed":False,"holdout_accessed":False,"sqcli_executed":False,
            "decision":"CONTINUE_STABILITY_GATE" if passing else "REJECT_FAMILY_BEFORE_SQ"}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--parquet",type=Path,required=True); p.add_argument("--config",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    result=run(a.parquet,json.loads(a.config.read_text())); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("attempted","passes","decision")},indent=2))


if __name__=="__main__": main()
