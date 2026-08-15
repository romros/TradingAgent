#!/usr/bin/env python3
import argparse,csv,datetime as dt,json
from pathlib import Path
from lab.sq_bridge.etf_relative_momentum_screen_v1 import sha
from lab.sq_bridge.etf_momentum60_transfer_screen_v1 import trades,stats
HERE=Path(__file__).resolve().parent;SPEC=HERE/'tech_momentum60_recent_holdout_preregistration_v1.json';LOCK=HERE/'tech_momentum60_recent_holdout_preregistration_v1.lock.json'
def load_authorized(path):
 out={}
 with path.open(newline='') as h:
  for row in csv.DictReader(h):
   day=dt.date.fromisoformat(row['date'])
   if day<dt.date(2024,9,1) or day>dt.date(2026,8,14):raise ValueError('ROW_OUTSIDE_AUTHORIZED_HOLDOUT')
   out[day]=(float(row['open']),float(row['close']))
 return out
def run(assets,parent,out):
 s=json.loads(SPEC.read_text());l=json.loads(LOCK.read_text());p=json.loads(parent.read_text())
 if sha(SPEC)!=l['preregistration_sha256'] or p['passing_assets']!=s['candidates']:raise ValueError('FROZEN_GATE_MISMATCH')
 result={};passing=[];g=s['asset_gate']
 for a,path in assets.items():
  x=stats(trades(load_authorized(path),dt.date(2025,1,1),dt.date(2026,8,14)));ok=x['trades']>=g['minimum_completed_trades'] and x['return']>g['minimum_net_return'] and (x['profit_factor'] or 999)>=g['minimum_profit_factor'] and x['maximum_drawdown']<=g['maximum_drawdown'];result[a]={'metrics':x,'pass':ok};passing+=([a] if ok else [])
 report={'decision':'PASS_RECENT_HOLDOUT' if passing else 'REJECT_RECENT_HOLDOUT','passing_assets':passing,'results':result,'source_sha256':{k:sha(v) for k,v in assets.items()},'performance_accessed':True,'next_gate':'SQ_NATIVE_AND_PORTFOLIO' if passing else None,'paper_authorized':False,'live_authorized':False};out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--parent',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run({k:Path(v) for k,v in(x.split('=',1) for x in a.asset)},a.parent,a.output),indent=2))
if __name__=='__main__':main()
