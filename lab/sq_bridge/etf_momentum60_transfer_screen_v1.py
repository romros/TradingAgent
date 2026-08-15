#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,json,math
from pathlib import Path
from lab.sq_bridge.etf_relative_momentum_screen_v1 import load,sha
HERE=Path(__file__).resolve().parent;SPEC=HERE/'etf_momentum60_transfer_preregistration_v1.json';LOCK=HERE/'etf_momentum60_transfer_preregistration_v1.lock.json'
def trades(frame,start,end,cost=.0025):
 d=sorted(frame);out=[]
 for i in range(61,len(d)-20):
  if d[i].month==d[i-1].month or not(start<=d[i] and d[i+20]<=end) or frame[d[i-1]][1]<=frame[d[i-61]][1]:continue
  out.append(frame[d[i+20]][0]/frame[d[i]][0]-1-cost)
 return out
def stats(v):
 eq=peak=1.;dd=0.;wins=loss=0.
 for x in v:eq*=1+x;peak=max(peak,eq);dd=max(dd,1-eq/peak);wins+=max(x,0);loss+=max(-x,0)
 return {'trades':len(v),'return':eq-1,'profit_factor':wins/loss if loss else None,'maximum_drawdown':dd}
def run(assets,out):
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text());assert sha(SPEC)==lock['preregistration_sha256'];bounds={k:tuple(map(dt.date.fromisoformat,v)) for k,v in spec['periods'].items()};res={};passing=[]
 for a,p in assets.items():
  f=load(p);period={k:stats(trades(f,*b)) for k,b in bounds.items()};combo=stats(trades(f,bounds['validation'][0],bounds['oos_2024'][1]));g=spec['asset_gate'];ok=all(x['return']>0 for x in period.values()) and (combo['profit_factor'] or 999)>=g['combined_validation_oos_minimum_profit_factor'] and combo['maximum_drawdown']<=g['combined_validation_oos_maximum_drawdown'] and combo['trades']>=g['combined_minimum_trades'];res[a]={'periods':period,'validation_plus_oos':combo,'pass':ok};passing+=([a] if ok else [])
 report={'decision':'PASS_ASSET_GATE_OPEN_RECENT_HOLDOUT' if passing else 'REJECT_TRANSFER_FAMILY','passing_assets':passing,'results':res,'source_sha256':{k:sha(v) for k,v in assets.items()},'holdout_2025_plus_accessed':False};out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run({k:Path(v) for k,v in(x.split('=',1) for x in a.asset)},a.output),indent=2))
if __name__=='__main__':main()
