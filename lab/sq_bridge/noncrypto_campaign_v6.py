#!/usr/bin/env python3
"""Run the sealed Alquimia v6 train and validation gates without retuning."""
from __future__ import annotations
import hashlib,itertools,json
from pathlib import Path
import numpy as np
import pandas as pd
from lab.sq_bridge.noncrypto_train_screen_v5 import atr,backtest,load

ROOT=Path(__file__).resolve().parents[2]; SPEC=ROOT/"lab/sq_bridge/noncrypto_campaign_preregistration_v6.json"; OUT=ROOT/"lab/sq_bridge/evidence/noncrypto_campaign_v6_results.json"
SEALED="86ed64eb08b05654d989110e9f4ebd1f76a974f41e0337e9a184c70d5b60a9bb"
EXITS={
 "V6_M15_A":{"stop":{"kind":"ATR","multiple":1.0},"target":{"kind":"R","multiple":1.5},"max_bars":8,"manager":{"kind":"NONE"}},
 "V6_M15_B":{"stop":{"kind":"ATR","multiple":1.25},"target":{"kind":"R","multiple":2.0},"max_bars":12,"manager":{"kind":"BREAK_EVEN","trigger_r":1.0}},
 "V6_M15_C":{"stop":{"kind":"ATR","multiple":1.5},"target":{"kind":"R","multiple":2.5},"max_bars":16,"manager":{"kind":"ATR_TRAIL","trigger_r":1.0,"atr_multiple":1.0}},
 "V6_D1_A":{"stop":{"kind":"ATR","multiple":1.0},"target":{"kind":"R","multiple":1.5},"max_bars":2,"manager":{"kind":"NONE"}},
 "V6_D1_B":{"stop":{"kind":"ATR","multiple":1.5},"target":{"kind":"R","multiple":2.0},"max_bars":3,"manager":{"kind":"BREAK_EVEN","trigger_r":1.0}},
 "V6_D1_C":{"stop":{"kind":"ATR","multiple":2.0},"target":{"kind":"R","multiple":2.5},"max_bars":5,"manager":{"kind":"ATR_TRAIL","trigger_r":1.0,"atr_multiple":1.0}}}

def session_fields(f,start,end,prefix):
 d=f.index.floor("D"); mask=(f.index.hour>=start)&(f.index.hour<end)
 return (f.high.where(mask).groupby(d).transform("max"),f.low.where(mask).groupby(d).transform("min"),pd.Series(mask,index=f.index).groupby(d).transform("sum"))
def signal(fid,f,a,p):
 if fid.startswith("xau-m15-failed-shock"):
  disp=f.close-f.close.shift(); ratio=a.shift().rolling(8).mean()/a.shift().rolling(64).mean(); out=pd.Series(0,index=f.index)
  for k in range(1,5):
   shock=(disp.shift(k).abs()>=p["shock_atr"]*a.shift(k+1))&(ratio.shift(k)<=p["max_fast_slow_atr_ratio"])
   out=out.mask((out==0)&shock&(disp.shift(k)<0)&(f.close>f.open.shift(k)),1);out=out.mask((out==0)&shock&(disp.shift(k)>0)&(f.close<f.open.shift(k)),-1)
  return out
 if fid.startswith("xau-m15-london"):
  hours=int(p["range_hours"]); hi,lo,c=session_fields(f,8-hours,8,"pre"); trade=(f.index.hour>=8)&(f.index.hour<12)&(c==hours*4); out=pd.Series(0,index=f.index)
  for k in range(1,int(p["failure_window_bars"])+1):
   inside=(f.close<hi)&(f.close>lo);out=out.mask((out==0)&trade&inside&(f.high.shift(k)>hi),-1);out=out.mask((out==0)&trade&inside&(f.low.shift(k)<lo),1)
  return out
 if fid.startswith("usdjpy-"):
  hi,lo,c=session_fields(f,0,7,"asia"); day=f.index.floor("D"); daily=(f.high.where(f.index.hour<7).groupby(day).max()-f.low.where(f.index.hour<7).groupby(day).min()); threshold=daily.shift().rolling(60,min_periods=40).quantile(p["range_quantile"]); q=day.map(threshold).to_numpy(); compact=(hi-lo)<=q; trade=(f.index.hour>=7)&(f.index.hour<12)&(c==28)
  if "breakout" in fid:
   n=int(p["trend_lookback_bars"]); trend=f.close.shift()-f.close.shift(n); return pd.Series(np.where(trade&compact&(f.close>hi)&(trend>0),1,np.where(trade&compact&(f.close<lo)&(trend<0),-1,0)),index=f.index)
  out=pd.Series(0,index=f.index); inside=(f.close<hi)&(f.close>lo)
  for k in range(1,int(p["failure_window_bars"])+1):out=out.mask((out==0)&trade&compact&inside&(f.high.shift(k)>hi),-1).mask((out==0)&trade&compact&inside&(f.low.shift(k)<lo),1)
  return out
 # EURUSD D1 exhaustion and same-bar reclaim/fade.
 prev=f.close.shift(); rng=f.high-f.low; down=(prev-f.low>=p["displacement_atr"]*a.shift())&(f.close>=f.low+p["reclaim_fraction"]*rng); up=(f.high-prev>=p["displacement_atr"]*a.shift())&(f.close<=f.high-p["reclaim_fraction"]*rng)
 return pd.Series(np.where(down,1,np.where(up,-1,0)),index=f.index)
def metric(f,a,s,e,fid,p,cost):return backtest(f,a,s,e,fid,p,cost=cost)
def gates(m,intra,stage):
 if stage=="train":return m["net_return"]>0 and m["profit_factor"]>=1.15 and m["max_drawdown"]<=.25 and m["trades"]>=(120 if intra else 30)
 return m["net_return"]>0 and m["profit_factor"]>=1.2 and m["max_drawdown"]<=.25 and m["trades"]>=(40 if intra else 12)
def main():
 if hashlib.sha256(SPEC.read_bytes()).hexdigest()!=SEALED:raise ValueError("v6 seal changed")
 spec=json.loads(SPEC.read_text()); frames={k:load(k) for k in spec["splits"]}; train=[]
 for fam in spec["families"]:
  full=frames[fam["market"]]; start,end=spec["splits"][fam["market"]]["train"]; f=full.loc[start:end]; a=atr(f); names=list(fam["axes"])
  for vals in itertools.product(*(fam["axes"][n] for n in names)):
   p=dict(zip(names,vals));s=signal(fam["id"],f,a,p)
   for ex in fam["exit_templates"]:
    m=metric(f,a,s,EXITS[ex],fam["id"],p,.0005);train.append({"family":fam["id"],"market":fam["market"],"parameters":p,"exit":ex,**m,"pass":gates(m,"M15" in fam["market"],"train")})
 selected=[]
 for fam in spec["families"]:
  rows=[r for r in train if r["family"]==fam["id"] and r["pass"]];rows.sort(key=lambda r:(r["profit_factor"],r["net_return"]),reverse=True);selected+=rows[:8]
 validation=[]
 for cand in selected:
  split=spec["splits"][cand["market"]]["validation"];f=frames[cand["market"]].loc[split[0]:split[1]];a=atr(f);s=signal(cand["family"],f,a,cand["parameters"]);e=EXITS[cand["exit"]]
  scenarios={n:metric(f,a,s,e,cand["family"],cand["parameters"],bps/10000) for n,bps in {"base":5,"conservative":8,"stress":15}.items()}
  years=[]
  for year in sorted(set(f.index.year)):
   fy=f.loc[str(year)];ay=a.loc[fy.index];sy=s.loc[fy.index];years.append(metric(fy,ay,sy,e,cand["family"],cand["parameters"],.0015)["net_return"]>0)
  passed=gates(scenarios["base"],"M15" in cand["market"],"validation") and scenarios["conservative"]["net_return"]>0 and scenarios["stress"]["profit_factor"]>=1.05 and scenarios["stress"]["net_return"]>0 and sum(years)/len(years)>=.6
  validation.append({"candidate":cand,"scenarios":scenarios,"positive_year_ratio":sum(years)/len(years),"pass_before_neighbors":passed})
 out={"schema_version":1,"decision":"V6_VALIDATION_COMPLETE","seal":SEALED,"train_combinations":len(train),"train_passes":sum(r["pass"] for r in train),"selected_for_validation":len(selected),"validation_passes_before_neighbors":sum(r["pass_before_neighbors"] for r in validation),"train":train,"validation":validation,"oos_accessed":False,"holdout_accessed":False,"retuned":False}
 OUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps({k:out[k] for k in ("decision","train_combinations","train_passes","selected_for_validation","validation_passes_before_neighbors")},sort_keys=True))
if __name__=="__main__":main()
