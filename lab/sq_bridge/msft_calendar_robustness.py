#!/usr/bin/env python3
"""Falsificació del candidat MSFT calendar: randomització i paràmetres ±10%."""
from __future__ import annotations
import argparse, copy, hashlib, json, math, random, sys
from pathlib import Path
import pandas as pd
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent))
from msft_python_validation import extract, load_data, simulate


def stress_metrics(trades, bps=36):
    values=[x["return"]-bps/10000 for x in trades]; curve=1.; win=loss=0.
    for x in values:
        curve*=1+x
        if x>0: win+=x
        else: loss-=x
    return {"return_pct":(curve-1)*100,"profit_factor":win/loss if loss else None,"trades":len(values)}


def monthly_random_signal(index, rng):
    signal=pd.Series(False,index=index)
    groups={}
    for value in index: groups.setdefault((value.year,value.month),[]).append(value)
    for dates in groups.values(): signal.loc[rng.choice(dates)]=True
    return signal


def set_slpt(contract, stop_mult, target_mult, atr_period):
    out=copy.deepcopy(contract); action=next(v for v in out["entries"].values() if v)["action"]
    sl=action["params"]["#StopLoss.StopLoss#"]; pt=action["params"]["#ProfitTarget.ProfitTarget#"]
    sl["params"]["#Value#"]*=stop_mult
    pt["params"]["#Value#"]*=target_mult; pt["params"]["#AtrPeriod#"]=atr_period
    return out


def run(sqx, simulations):
    contract=extract(sqx); frame=load_data("1998-01-01","2026-08-02")
    periods={"validation":("2012-10-17","2018-04-23"),"oos":("2018-04-24","2023-10-29"),"holdout":("2023-10-30","2026-08-01")}
    base={p:simulate(frame,contract,*dates) for p,dates in periods.items()}
    base_stress={p:stress_metrics(x["trades_detail"]) for p,x in base.items()}
    seed=int(hashlib.sha256(sqx.read_bytes()).hexdigest()[:16],16); rng=random.Random(seed)
    random_results={}
    for period,dates in periods.items():
        start=pd.Timestamp(dates[0]); end=pd.Timestamp(dates[1])
        # Warm-up ampli; el simulador també impedeix entrades abans que ATR existeixi.
        sample=frame.loc[(frame.index >= start-timedelta(days=400)) & (frame.index <= end)]
        returns=[]
        for _ in range(simulations):
            result=simulate(sample,contract,*dates,signal_override=monthly_random_signal(sample.index,rng))
            returns.append(stress_metrics(result["trades_detail"])["return_pct"])
        observed=base_stress[period]["return_pct"]
        random_results[period]={"simulations":simulations,"observed_stress_return_pct":observed,
          "random_median_return_pct":sorted(returns)[len(returns)//2],
          "familywise_empirical_p":(1+sum(x>=observed for x in returns))/(simulations+1)}
    perturb=[]
    for sm in (.9,1.,1.1):
      for tm in (.9,1.,1.1):
       for ap in (18,20,22):
        variant=set_slpt(contract,sm,tm,ap); results={}
        for period in ("validation","oos"):
            dates=periods[period]; start=pd.Timestamp(dates[0]); end=pd.Timestamp(dates[1])
            sample=frame.loc[(frame.index >= start-timedelta(days=400)) & (frame.index <= end)]
            results[period]=stress_metrics(simulate(sample,variant,*dates)["trades_detail"])
        passed=all(x["trades"]>=25 and (x["profit_factor"] or 0)>=1.1 and x["return_pct"]>0 for x in results.values())
        perturb.append({"stop_multiplier":sm,"target_multiplier":tm,"target_atr_period":ap,"passed":passed,"results":results})
    return {"schema_version":1,"candidate":"MSFT calendar long Strategy 0.14","sqx_sha256":hashlib.sha256(sqx.read_bytes()).hexdigest(),
      "cost_stress_roundtrip_bps":36,"base":base_stress,"random_monthly_entry_benchmark":random_results,
      "parameter_perturbation":{"grid_size":len(perturb),"pass_ratio":sum(x["passed"] for x in perturb)/len(perturb),"variants":perturb},
      "interpretation":"Random benchmark preserves one entry opportunity per month; parameter selection uses validation and OOS only."}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--sqx",type=Path,required=True); p.add_argument("--simulations",type=int,default=2000); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    result=run(a.sqx,a.simulations); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"base":result["base"],"random":result["random_monthly_entry_benchmark"],"perturbation_pass_ratio":result["parameter_perturbation"]["pass_ratio"]},indent=2))
if __name__=="__main__": main()
