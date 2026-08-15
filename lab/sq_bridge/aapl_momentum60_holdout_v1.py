#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json
from datetime import date
from pathlib import Path
H=Path(__file__).resolve().parent;S=H/'aapl_momentum60_holdout_preregistration_v1.json'
def main():
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--output',type=Path,required=True);z=a.parse_args();spec=json.loads(S.read_text());rows=[]
 for x in csv.reader(z.source.open(newline='',encoding='utf-8-sig')):
  if not x or x[0].lower()=='date':continue
  d=date.fromisoformat(x[0].replace('.','-'));off=2 if '.' in x[0] else 1;rows.append((d,*map(float,x[off:off+4])))
 c=[x[4] for x in rows];found=[];last=-1
 for i in range(60,len(rows)-22):
  # SQ can close an ExitAfterBars position and open the next one at the same
  # bar open, so equality is allowed; only a genuinely overlapping entry is not.
  if rows[i][0].month==rows[i+1][0].month or i+1<last or c[i]<=c[i-60]:continue
  en=i+1;ex=en+20
  if date.fromisoformat(spec['holdout'][0])<=rows[en][0]<=date.fromisoformat(spec['holdout'][1]):found.append({'entry':rows[en][0].isoformat(),'exit':rows[ex][0].isoformat(),'entry_price':rows[en][1],'exit_price':rows[ex][1],'net_return':rows[ex][1]/rows[en][1]-1-.003})
  last=ex
 gp=sum(max(x['net_return'],0) for x in found);gl=sum(max(-x['net_return'],0) for x in found);eq=pk=1.;dd=0
 for x in found:eq*=1+x['net_return'];pk=max(pk,eq);dd=max(dd,1-eq/pk)
 m={'trades':len(found),'return':eq-1,'profit_factor':gp/gl if gl else None,'maximum_drawdown':dd};g=spec['gates'];ok=m['trades']>=g['minimum_trades'] and (m['profit_factor'] or 0)>=g['minimum_profit_factor'] and m['return']>0 and m['maximum_drawdown']<=g['maximum_drawdown']
 economics={}
 for capital in (500,1000):
  equity=float(capital);peak=equity;maxdd=0;wins=losses=0.
  for x in found:
   entry=x['entry_price']*1.001;exitp=x['exit_price']*.999;shares=int(equity//entry)
   pnl=shares*(exitp-entry)-2 if shares else 0;equity+=pnl;peak=max(peak,equity);maxdd=max(maxdd,1-equity/peak);wins+=max(pnl,0);losses+=max(-pnl,0)
  economics[str(capital)]={'return_pct':(equity/capital-1)*100,'profit_factor':wins/losses if losses else None,'maximum_drawdown_pct':maxdd*100,'final_equity':equity}
 out={'schema_version':1,'decision':'PASS_TO_NATIVE_SQ' if ok else 'REJECT_HOLDOUT','preregistration_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(z.source.read_bytes()).hexdigest(),'metrics':m,'whole_share_ibkr_stress':economics,'trades':found,'holdout_accessed':True,'paper_authorized':False,'live_authorized':False};z.output.parent.mkdir(parents=True,exist_ok=True);z.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
