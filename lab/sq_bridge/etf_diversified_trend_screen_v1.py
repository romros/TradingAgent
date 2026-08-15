#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from lab.sq_bridge.etf_relative_momentum_screen_v1 import load, metrics, reviews, sha
HERE=Path(__file__).resolve().parent; SPEC=HERE/'etf_diversified_trend_preregistration_v1.json'; LOCK=HERE/'etf_diversified_trend_preregistration_v1.lock.json'
def rows(frames,n,start,end):
    days=sorted(set.intersection(*(set(x) for x in frames.values()))); points=reviews(days); out=[]
    for p,signal in enumerate(points[:-1]):
        if p+1<n: continue
        nxt=points[p+1]
        if signal+1>=len(days) or nxt+1>=len(days):continue
        entry,exit=days[signal+1],days[nxt+1]
        if not(start<=entry and exit<=end):continue
        eligible=[]
        for asset,frame in frames.items():
            history=[frame[days[points[i]]][1] for i in range(p-n+1,p+1)]
            if history[-1]>sum(history)/n:eligible.append(asset)
        value=sum(frames[a][exit][0]/frames[a][entry][0]-1 for a in eligible)/5
        out.append({'entry':entry,'return':value,'selected':eligible})
    return out
def one(rows_):
    r=metrics(rows_);r.pop('cash_slot_months',None);r['cash_sleeve_months']=sum(5-len(x['selected']) for x in rows_);return r
def run(assets,output):
    spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
    if sha(SPEC)!=lock['preregistration_sha256']:raise ValueError('FROZEN_CONTRACT_MISMATCH')
    frames={k:load(v) for k,v in assets.items()}; bounds={k:tuple(map(dt.date.fromisoformat,v)) for k,v in spec['periods'].items()}; results={}
    for n in spec['rule']['variants_months']:results[str(n)]={s:one(rows(frames,n,*bounds[s])) for s in ('train','validation')}
    gate=spec['validation_gate'];central=results[str(spec['rule']['central_months'])]['validation'];passed=all(x['validation']['total_return']>0 for x in results.values()) and central['annualized_sharpe']>=gate['central_minimum_sharpe'] and central['maximum_drawdown']<=gate['central_maximum_drawdown'] and central['monthly_observations']>=gate['minimum_months']
    report={'decision':'PASS_VALIDATION_FREEZE_BEFORE_OOS' if passed else 'REJECT_VALIDATION','results':results,'source_sha256':{k:sha(v) for k,v in assets.items()},'preregistration_sha256':sha(SPEC),'oos_2024_accessed_for_this_family':False,'holdout_2025_plus_accessed':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();assets={k:Path(v) for k,v in(x.split('=',1) for x in a.asset)};print(json.dumps(run(assets,a.output),indent=2))
if __name__=='__main__':main()
