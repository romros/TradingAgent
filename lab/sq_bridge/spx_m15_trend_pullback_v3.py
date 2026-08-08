#!/usr/bin/env python3
"""Development-only RSI pullback screen for SPX M15."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from spx_m15_compression_expansion_v2 import load_m15, leverage_plan, metrics


def rsi(close, period: int):
    delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    relative_strength = avg_gain / avg_loss
    return (100 - 100/(1 + relative_strength)).where(avg_loss != 0, 100)


def parameter_grid(config: dict):
    keys=tuple(config["grid"])
    for values in itertools.product(*(config["grid"][key] for key in keys)):
        yield dict(zip(keys,values))


def simulate(frame, p: dict, account: dict, costs: dict):
    trend=frame.close.ewm(span=p["trend_ema_bars"],adjust=False,min_periods=p["trend_ema_bars"]).mean()
    oscillator=rsi(frame.close,p["rsi_bars"])
    start,end=p["entry_window_ny"]
    if p["side"]=="long": signal=(frame.close>trend)&(oscillator<=p["rsi_extreme"]); direction=1
    else: signal=(frame.close<trend)&(oscillator>=100-p["rsi_extreme"]); direction=-1
    signal &= frame.hour_ny.between(start,end)&(frame.weekday<5)&frame.complete
    o,h,l,c,atr,complete=(frame[x].to_numpy() for x in ("open","high","low","close","atr","complete"))
    years=frame.year.to_numpy(); trades=[]; last_exit=-1
    for at in np.flatnonzero(signal.fillna(False).to_numpy()):
        entry_i=at+1
        if entry_i>=len(frame) or entry_i<=last_exit or not complete[entry_i]: continue
        entry=float(o[entry_i]); stop_distance=p["stop_atr"]*float(atr[at])/entry
        plan=leverage_plan(stop_distance,account)
        if plan is None: continue
        stop=entry-direction*p["stop_atr"]*float(atr[at]); target=entry+direction*p["target_atr"]*float(atr[at])
        exit_i=min(entry_i+p["hold_bars"]-1,len(frame)-1); exit_price=float(c[exit_i]); reason="time"; invalid=False
        for i in range(entry_i,exit_i+1):
            if not complete[i]: invalid=True; exit_i=i; break
            stop_hit=l[i]<=stop if direction==1 else h[i]>=stop
            target_hit=h[i]>=target if direction==1 else l[i]<=target
            if stop_hit: exit_i=i; exit_price=min(float(o[i]),stop) if direction==1 else max(float(o[i]),stop); reason="stop"; break
            if target_hit: exit_i=i; exit_price=max(float(o[i]),target) if direction==1 else min(float(o[i]),target); reason="target"; break
        last_exit=exit_i
        if invalid: continue
        gross=direction*(exit_price/entry-1)
        trade={"year":int(years[entry_i]),"gross":gross,"leverage":plan["leverage"],"margin":plan["margin"],"reason":reason}
        for name,bps in costs.items(): trade[name]=plan["exposure"]*(gross-bps/10_000)-0.1/account["capital_usdc"]
        trades.append(trade)
    return trades


def run(parquet: Path, config: dict):
    frame=load_m15(parquet); rows=[]; gate=config["development_gate"]
    for p in parameter_grid(config):
        trades=simulate(frame,p,config["small_account"],config["costs_bps"])
        measured={name:metrics(trades,name) for name in config["costs_bps"]}; stress=measured["stress"]
        passed=(stress["trades"]>=gate["minimum_trades"] and (stress["profit_factor"] or 0)>=gate["minimum_stress_profit_factor"]
                and stress["positive_year_ratio"]>=gate["minimum_positive_year_ratio"] and stress["drawdown_pct"]<=gate["maximum_stress_drawdown_pct"]
                and (stress["expectancy_usdc"] or -999)>=gate["minimum_stress_expectancy_usdc"])
        rows.append({"parameters":p,"metrics":measured,"passes":bool(passed)})
    passing=[row for row in rows if row["passes"]]
    eligible=[row for row in rows if row["metrics"]["stress"]["trades"]>=gate["minimum_trades"]]
    return {"schema_version":1,"family":config["id"],"attempted":len(rows),"passes":len(passing),
            "passing":passing,"top_20":sorted(rows,key=lambda row:(row["metrics"]["stress"]["profit_factor"] or 0),reverse=True)[:20],
            "diagnostics":{"maximum_trades":max(row["metrics"]["stress"]["trades"] for row in rows),
                "points_with_minimum_trades":len(eligible),
                "best_stress_pf_with_minimum_trades":max((row["metrics"]["stress"]["profit_factor"] or 0 for row in eligible),default=None),
                "best_base_pf_with_minimum_trades":max((row["metrics"]["base"]["profit_factor"] or 0 for row in eligible),default=None)},
            "validation_accessed":False,"holdout_accessed":False,"sqcli_executed":False,
            "decision":"CONTINUE_STABILITY_GATE" if passing else "REJECT_FAMILY_BEFORE_SQ"}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--parquet",type=Path,required=True); p.add_argument("--config",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    result=run(a.parquet,json.loads(a.config.read_text())); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("attempted","passes","decision")},indent=2))


if __name__=="__main__": main()
