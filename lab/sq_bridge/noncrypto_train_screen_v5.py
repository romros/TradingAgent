#!/usr/bin/env python3
"""Exact, performance-blind train screen for the sealed Alquimia v5 surfaces."""
from __future__ import annotations

import hashlib, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "lab/sq_bridge/evidence/noncrypto_sq_build_plan_v5.json"
OUTPUT = ROOT / "lab/sq_bridge/evidence/noncrypto_train_screen_v5.json"
SOURCES = {
 "XAUUSD_M15": Path("/mnt/volume-SQ/user/exports/alquimia_v5_xau_train/XAUUSD_M1_dukasXAUUSD_M1_dukas_NYclose-M1-No Session.csv"),
 "USDJPY_M15": Path("/mnt/volume-SQ/user/exports/alquimia_usdjpy_source/USDJPY_M1_dukas-M1-No Session.csv"),
 "EURUSD_D1": Path("/mnt/volume-SQ/user/exports/alquimia_eurusd_v4_ny17_v3_roundtrip/EURUSD_ALQ_NY17_D1_V3-D1-No Session.csv"),
 "US500_D1": Path("/mnt/volume-SQ/user/exports/alquimia_us500_rth_d1_roundtrip_v2/US500_ALQ_RTH_D1-D1-No Session.csv")}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(key):
    p=SOURCES[key]; f=pd.read_csv(p,header=None,names="date time open high low close volume".split())
    f.index=pd.to_datetime(f.date+" "+f.time,format="%Y.%m.%d %H:%M",utc=True)
    f=f[["open","high","low","close"]].astype(float).sort_index(); f=f[~f.index.duplicated(keep="last")]
    if key.endswith("M15"):
        f=f.resample("15min",origin="start_day").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
        day=f.index.floor("D"); asia=f.index.hour<7
        f["_asia_high"]=f.high.where(asia).groupby(day).transform("max")
        f["_asia_low"]=f.low.where(asia).groupby(day).transform("min")
        f["_asia_count"]=pd.Series(asia,index=f.index).groupby(day).transform("sum")
    return f
def atr(f):
    pc=f.close.shift(); tr=pd.concat([f.high-f.low,(f.high-pc).abs(),(f.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(14).mean()
def signals(h,f,a,p):
    if h.startswith("xau-m15-macro"):
        x,y=p["channel_bars"],p["compression_quantile"]
        n=a/f.close; comp=n.shift().le(n.shift(2).rolling(95).quantile(y)); hi=f.high.shift().rolling(x).max(); lo=f.low.shift().rolling(x).min()
        return pd.Series(np.where(comp&(f.close>hi),1,np.where(comp&(f.close<lo),-1,0)),index=f.index)
    if h.startswith("xau-m15-failed"):
        x,y=p["shock_atr"],p["reentry_bars"]
        out=pd.Series(0,index=f.index); disp=f.close-f.close.shift(); shock=(disp.abs()>=x*a.shift())
        for k in range(1,int(y)+1):
            up=shock.shift(k,fill_value=False)&(disp.shift(k)>0)&(f.close<f.open.shift(k)); dn=shock.shift(k,fill_value=False)&(disp.shift(k)<0)&(f.close>f.open.shift(k)); out=out.mask((out==0)&up,-1).mask((out==0)&dn,1)
        return out
    if h.startswith("usdjpy-"):
        day=f.index.floor("D"); asia=f.index.hour<7
        ah=f._asia_high; al=f._asia_low; cnt=f._asia_count
        london=(f.index.hour>=7)&(f.index.hour<12)&(cnt==28)
        if "range-breakout" in h:
            x,y=p["max_range_atr_ratio"],p["trend_lookback_bars"]
            trend=f.close.shift()-f.close.shift(int(y)); compact=(ah-al)<=x*a.shift()
            return pd.Series(np.where(london&compact&(f.close>ah)&(trend>0),1,np.where(london&compact&(f.close<al)&(trend<0),-1,0)),index=f.index)
        x,y=p["failure_window_bars"],p["break_buffer_atr"]
        out=pd.Series(0,index=f.index); inside=(f.close>al)&(f.close<ah)
        for k in range(1,int(x)+1):
            out=out.mask((out==0)&london&inside&(f.high.shift(k)>ah+y*a.shift()),-1)
            out=out.mask((out==0)&london&inside&(f.low.shift(k)<al-y*a.shift()),1)
        return out
    if h.startswith("us500-"):
        x,y=p["shock_atr"],p["reclaim_fraction"]
        pc=f.close.shift(); reclaim=f.close>=f.low+y*(f.high-f.low); tr=pd.concat([f.high-f.low,(f.high-pc).abs(),(f.low-pc).abs()],axis=1).max(axis=1)
        calm=tr.shift().rolling(5).mean()<=tr.shift().rolling(20).mean(); return pd.Series(np.where((pc-f.low>=x*a.shift())&reclaim&calm,1,0),index=f.index)
    x,y=p["channel_days"],p["trend_lookback_days"]
    hi=f.high.shift().rolling(int(x)).max(); lo=f.low.shift().rolling(int(x)).min(); trend=f.close.shift()-f.close.shift(int(y))
    return pd.Series(np.where((f.close>hi)&(trend>0),1,np.where((f.close<lo)&(trend<0),-1,0)),index=f.index)

def initial_geometry(f,a,i,d,e,h,p):
    entry=float(f.open.iloc[i+1]); av=float(a.iloc[i]); sk=e["stop"]; kind=sk["kind"]
    if kind=="ATR": stop=entry-d*sk["multiple"]*av
    elif "SHOCK_LOW" in kind: stop=float(f.low.iloc[i])-sk["multiple"]*av
    elif "SHOCK_EXTREME" in kind:
        window=int(p["reentry_bars"]); candidates=[]
        for k in range(1,window+1):
            displacement=float(f.close.iloc[i-k]-f.close.iloc[i-k-1])
            threshold=float(p["shock_atr"]*a.iloc[i-k-1])
            if ((d>0 and displacement<=-threshold)
                    or (d<0 and displacement>=threshold)): candidates.append(i-k)
        if not candidates:return None
        shock=max(candidates); ref=float(f.low.iloc[shock] if d>0 else f.high.iloc[shock]); stop=ref-d*sk["multiple"]*av
    elif "FAILED_BREAK_EXTREME" in kind:
        window=int(p["failure_window_bars"]); z=f.iloc[max(0,i-window):i]
        ref=float(z.low.min() if d>0 else z.high.max()); stop=ref-d*sk["multiple"]*av
    elif "ASIA_OPPOSITE" in kind:
        ref=float(f._asia_low.iloc[i] if d>0 else f._asia_high.iloc[i]); cap=entry-d*sk["atr_cap"]*av; stop=max(ref,cap) if d>0 else min(ref,cap)
    elif "OPPOSITE_CHANNEL" in kind:
        ref=float(f.low.iloc[max(0,i-30):i].min()) if d>0 else float(f.high.iloc[max(0,i-30):i].max()); cap=entry-d*sk["atr_cap"]*av; stop=max(ref,cap) if d>0 else min(ref,cap)
    else: return None
    r=d*(entry-stop)
    if not np.isfinite(r) or r<=0: return None
    t=e["target"]; target=entry+d*t.get("multiple",t.get("fallback_r",1.5))*r
    if "MIDPOINT" in t["kind"]:
        if "ASIA" in t["kind"]:
            structural=(float(f._asia_high.iloc[i])+float(f._asia_low.iloc[i]))/2
        else: structural=(float(f.high.iloc[max(0,i-8):i].max())+float(f.low.iloc[max(0,i-8):i].min()))/2
        if d*(structural-entry)>0: target=structural
    return entry,stop,target,r

def backtest(f,a,s,e,h,p,cost=.0005):
    trades=[]; busy=-1
    for i in np.flatnonzero(s.to_numpy()!=0):
        if i<=busy or i+1>=len(f) or not np.isfinite(a.iloc[i]): continue
        d=int(s.iloc[i]); g=initial_geometry(f,a,i,d,e,h,p)
        if g is None: continue
        entry,stop,target,r=g; end=min(len(f)-1,i+1+e["max_bars"]); exitp=float(f.open.iloc[end]); reason="TIME"; manager=e["manager"]
        for j in range(i+1,end):
            hitstop=f.low.iloc[j]<=stop if d>0 else f.high.iloc[j]>=stop; hittp=f.high.iloc[j]>=target if d>0 else f.low.iloc[j]<=target
            if hitstop: exitp=stop; reason="SL"; end=j; break
            if hittp: exitp=target; reason="TP"; end=j; break
            favorable=d*(float(f.close.iloc[j])-entry)/r
            candidate=None; kind=manager["kind"]
            if kind=="BREAK_EVEN" and favorable>=manager["trigger_r"]: candidate=entry
            elif kind=="ATR_TRAIL" and favorable>=manager["trigger_r"]: candidate=float(f.close.iloc[j])-d*manager["atr_multiple"]*float(a.iloc[j])
            elif kind=="TWO_BAR_STRUCTURE_TRAIL" and favorable>=manager["trigger_r"]:
                z=f.iloc[max(i+1,j-1):j+1]; candidate=float(z.low.min() if d>0 else z.high.max())
            elif kind=="ASIA_BREAK_EDGE_TRAIL" and favorable>=manager["trigger_r"]: candidate=float(f._asia_high.iloc[i] if d>0 else f._asia_low.iloc[i])
            elif kind=="BREAK_EVEN_AT_ASIA_MIDPOINT":
                midpoint=(float(f._asia_high.iloc[i])+float(f._asia_low.iloc[i]))/2
                if d*(float(f.close.iloc[j])-midpoint)>=0: candidate=entry
            elif kind=="PREVIOUS_DAILY_LOW_TRAIL" and favorable>=manager["trigger_r"]: candidate=float(f.low.iloc[j-1])
            elif kind=="FIVE_BAR_CHANNEL_OR_ATR_TRAIL" and favorable>=manager["trigger_r"]:
                z=f.iloc[max(i+1,j-4):j+1]; structure=float(z.low.min() if d>0 else z.high.max()); avtrail=float(f.close.iloc[j])-d*manager["atr_multiple"]*float(a.iloc[j]); candidate=max(structure,avtrail) if d>0 else min(structure,avtrail)
            if candidate is not None: stop=max(stop,candidate) if d>0 else min(stop,candidate)
            if manager.get("early_exit")=="CLOSE_BELOW_SMA5_NEXT_OPEN" and j>=4 and float(f.close.iloc[j])<float(f.close.iloc[j-4:j+1].mean()):
                end=j+1; exitp=float(f.open.iloc[end]) if end<len(f) else float(f.close.iloc[j]); reason="MA_EXIT"; break
        ret=d*(exitp-entry)/entry-cost; trades.append(ret); busy=end
    if not trades:return {"trades":0,"net_return":0,"profit_factor":0,"max_drawdown":0}
    v=np.array(trades); gains=v[v>0].sum(); losses=-v[v<0].sum(); eq=np.cumprod(1+v); peak=np.maximum.accumulate(np.r_[1,eq]); dd=(peak[1:]-eq)/peak[1:]
    return {"trades":len(v),"net_return":float(eq[-1]-1),"profit_factor":float(gains/losses if losses else 99),"max_drawdown":float(dd.max()),"win_rate":float((v>0).mean())}

def main():
    plan=json.loads(PLAN.read_text()); frames={}; results=[]
    for key in SOURCES:
        frames[key]=load(key)
    for job in plan["jobs"]:
        f=frames[job["market_key"]]; lo,hi=job["train_period"]; f=f.loc[lo:hi]; a=atr(f); names=list(job["numeric_axes"]); axes=[job["numeric_axes"][name] for name in names]
        for values in itertools.product(*axes):
            params=dict(zip(names,values)); s=signals(job["hypothesis_id"],f,a,params); m=backtest(f,a,s,job["exit_semantics"],job["hypothesis_id"],params)
            results.append({"job_id":job["job_id"],"hypothesis_id":job["hypothesis_id"],"parameters":params,**m})
    for r in results:
        intraday="-m15-" in r["hypothesis_id"]; r["train_gate_pass"]=(r["net_return"]>0 and r["profit_factor"]>=1.15 and r["max_drawdown"]<=.25 and r["trades"]>=(120 if intraday else 30))
    ranked=sorted(results,key=lambda r:(r["train_gate_pass"],r["profit_factor"],r["net_return"]),reverse=True)
    out={"schema_version":1,"decision":"TRAIN_SCREEN_COMPLETE","performance_scope":"TRAIN_ONLY","validation_accessed":False,"oos_accessed":False,"holdout_accessed":False,"cost_roundtrip_bps":5,"source_sha256":{k:sha(v) for k,v in SOURCES.items()},"combinations":len(results),"passing":sum(r["train_gate_pass"] for r in results),"top":ranked[:30],"all_results":results}
    OUTPUT.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); print(json.dumps({k:out[k] for k in ("decision","combinations","passing")},sort_keys=True))
if __name__=="__main__": main()
