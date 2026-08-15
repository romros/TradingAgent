#!/usr/bin/env python3
"""Evaluate frozen JPM Momentum 60 on the untouched 2025-2026 holdout."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path
H=Path(__file__).resolve().parent;S=H/'jpm_momentum60_holdout_preregistration_v1.json'
def metrics(trades,capital):
 equity=float(capital);peak=equity;dd=wins=losses=0.
 for t in trades:
  entry=t['entry_price']*1.001;exitp=t['exit_price']*.999;shares=math.floor(equity/entry);pnl=shares*(exitp-entry)-2*max(1,.005*shares) if shares else 0;equity+=pnl;peak=max(peak,equity);dd=max(dd,1-equity/peak);wins+=max(pnl,0);losses+=max(-pnl,0)
 return {'trades':len(trades),'return_pct':(equity/capital-1)*100,'profit_factor':wins/losses if losses else None,'maximum_drawdown_pct':dd*100,'final_equity':equity}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();spec=json.loads(S.read_text());rows=[]
 for x in csv.reader(a.source.open(newline='',encoding='utf-8-sig')):
  if not x or x[0].lower()=='date':continue
  d=date.fromisoformat(x[0].replace('.','-'));off=2 if '.' in x[0] else 1;rows.append((d,*map(float,x[off:off+4])))
 c=[x[4] for x in rows];start,end=map(date.fromisoformat,spec['holdout']);found=[];last=-1
 for i in range(60,len(rows)-21):
  if rows[i][0].month==rows[i+1][0].month or i+1<last or c[i]<=c[i-60]:continue
  en=i+1;ex=en+20;last=ex
  if start<=rows[en][0] and rows[ex][0]<=end:found.append({'entry':rows[en][0].isoformat(),'exit':rows[ex][0].isoformat(),'entry_price':rows[en][1],'exit_price':rows[ex][1]})
 econ={str(k):metrics(found,k) for k in (500,1000)};m=econ['500'];g=spec['gates'];ok=m['trades']>=g['minimum_completed_trades'] and (m['profit_factor'] or 0)>=g['minimum_stress_profit_factor'] and m['return_pct']>0 and m['maximum_drawdown_pct']<=g['maximum_stress_drawdown_pct']
 out={'schema_version':1,'decision':'PASS_TO_NATIVE_SQ' if ok else 'REJECT_HOLDOUT','preregistration_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'whole_share_ibkr_stress':econ,'completed_trades':found,'holdout_accessed':True,'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
