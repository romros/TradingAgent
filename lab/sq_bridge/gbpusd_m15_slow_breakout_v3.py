#!/usr/bin/env python3
"""Frozen slow-breakout follow-up after rejecting high-turnover Donchian v2."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path

from lab.sq_bridge.gbpusd_m15_v1 import SPLITS, load_m15
from lab.sq_bridge.gbpusd_m15_donchian_v2 import metrics, segment, simulate


def gate(periods):
    v, o = periods["validation"], periods["oos"]
    return (v["base"]["n"] >= 25 and o["base"]["n"] >= 25
            and v["base"]["pf"] >= 1.2 and o["base"]["pf"] >= 1.2
            and v["stress"]["pf"] >= 1.05 and o["stress"]["pf"] >= 1.05
            and v["stress"]["ev_usdc"] >= .1 and o["stress"]["ev_usdc"] >= .1
            and v["base"]["positive_year_ratio"] >= .6 and o["base"]["positive_year_ratio"] >= .6
            and v["base"]["dd_pct"] <= 25 and o["base"]["dd_pct"] <= 25)


def run(path: Path):
    data = load_m15(path); families=[]
    for side,name in ((1,"slow_breakout_long"),(-1,"slow_breakout_short")):
        variants=[]
        for channel in (192,384,768):
            for minimum_hold in (96,192):
                t=simulate(data,channel,3.0,side,minimum_hold=minimum_hold)
                train=metrics(segment(t,"train"),15)
                score=train["pf"]*math.sqrt(train["n"]) if train["n"]>=25 and train["ev_usdc"]>0 else -1
                variants.append((score,channel,minimum_hold,t,train))
        _,channel,minimum_hold,selected,train=max(variants,key=lambda x:x[0])
        periods={split:{scenario:metrics(segment(selected,split),cost) for scenario,cost in (("base",8),("conservative",15),("stress",30))} for split in SPLITS}
        families.append({"family":name,"selected_on_train":{"channel":channel,"minimum_hold":minimum_hold,"atr_multiple":3.0},"train_selection_metric_at_15bps":train,"periods":periods,"passes_pre_holdout":gate(periods)})
    eligible=[x["family"] for x in families if x["passes_pre_holdout"]]
    return {"methodology":"methodology_gbpusd_m15_slow_breakout_v3.json","source":str(path),"attempted_variants":12,"holdout_evaluated":False,"families":families,"eligible":eligible,"decision":"PASS_TO_SQCLI" if eligible else "REJECT_NO_SQCLI"}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    result=run(a.input); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))


if __name__=="__main__": main()
