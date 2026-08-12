#!/usr/bin/env python3
"""Frozen validation of the sole Alquimia v5 train survivor."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from lab.sq_bridge.noncrypto_train_screen_v5 import PLAN, OUTPUT as TRAIN, atr, backtest, load, signals

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/"lab/sq_bridge/evidence/noncrypto_validation_v5.json"
HYP="eurusd-d1-short-horizon-trend-v5"; JOB=f"{HYP}__exit-2"

def main():
    train=json.loads(TRAIN.read_text()); plan=json.loads(PLAN.read_text())
    survivors=[r for r in train["all_results"] if r["train_gate_pass"]]
    if len(survivors)!=1 or survivors[0]["job_id"]!=JOB or survivors[0]["parameters"]!={"channel_days":5,"trend_lookback_days":40}:
        raise ValueError("frozen train survivor mismatch")
    job=next(j for j in plan["jobs"] if j["job_id"]==JOB)
    if job["exit_semantics"]!={"stop":{"kind":"ATR","multiple":1.5},"target":{"kind":"R","multiple":2.0},"max_bars":5,"manager":{"kind":"BREAK_EVEN","trigger_r":1.0}}:
        raise ValueError("frozen exit mismatch")
    f=load("EURUSD_D1").loc["2018-01-01":"2021-12-31"]; a=atr(f)
    params={"channel_days":5,"trend_lookback_days":40}; s=signals(HYP,f,a,params)
    scenarios={name:backtest(f,a,s,job["exit_semantics"],HYP,params,cost=bps/10000)
               for name,bps in {"base":5,"conservative":8,"stress":15}.items()}
    years={}
    for year in range(2018,2022):
        fy=f.loc[str(year)]; ay=atr(f).loc[fy.index]; sy=signals(HYP,f,a,params).loc[fy.index]
        years[str(year)]=backtest(fy,ay,sy,job["exit_semantics"],HYP,params,cost=.0015)
    neighbors=[]
    for channel in (4,5,6):
        for trend in (36,40,44):
            if (channel,trend)==(5,40): continue
            p={"channel_days":channel,"trend_lookback_days":trend}; ns=signals(HYP,f,a,p)
            m=backtest(f,a,ns,job["exit_semantics"],HYP,p,cost=.0015)
            neighbors.append({"parameters":p,**m,"positive":m["net_return"]>0})
    positive_years=sum(v["net_return"]>0 for v in years.values())/4
    positive_neighbors=sum(v["positive"] for v in neighbors)/len(neighbors)
    base,stress=scenarios["base"],scenarios["stress"]
    passed=(base["net_return"]>0 and scenarios["conservative"]["net_return"]>0
            and base["profit_factor"]>=1.2 and stress["profit_factor"]>=1.05
            and stress["net_return"]>0 and base["max_drawdown"]<=.25
            and base["trades"]>=12 and positive_years>=.6 and positive_neighbors>=.7)
    out={"schema_version":1,"decision":"PASS_VALIDATION" if passed else "REJECT_VALIDATION",
         "candidate":survivors[0],"period":["2018-01-01","2021-12-31"],
         "scenarios":scenarios,"stress_calendar_years":years,
         "positive_calendar_year_ratio":positive_years,"neighbors":neighbors,
         "positive_neighbors_ratio":positive_neighbors,"validation_accessed":True,
         "oos_accessed":False,"holdout_accessed":False,"retuned":False,
         "train_receipt_sha256":hashlib.sha256(TRAIN.read_bytes()).hexdigest()}
    OUTPUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"decision":out["decision"],"scenarios":scenarios,
          "positive_calendar_year_ratio":positive_years,"positive_neighbors_ratio":positive_neighbors},sort_keys=True))
if __name__=="__main__":main()
