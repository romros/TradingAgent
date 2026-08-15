#!/usr/bin/env python3
"""Frozen GLD D1 breakout train/validation and single OOS evaluator."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path
SPEC=Path(__file__).with_name('gld_d1_breakout_preregistration_v1.json')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(path,allow_oos=False):
 rows=[]
 for raw in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not raw or raw[0].lower()=='date': continue
  day=date.fromisoformat(raw[0].replace('.','-'))
  if not allow_oos and day>=date(2024,1,1): raise ValueError('OOS leaked into development')
  offset=2 if len(raw)>1 and ':' in raw[1] else 1;rows.append((day,float(raw[offset]),float(raw[offset+3])))
 if not rows or any(a[0]>=b[0] for a,b in zip(rows,rows[1:])): raise ValueError('rows must be ordered and unique')
 return rows
def trades(rows,entry_n,exit_n):
 closes=[x[2] for x in rows];out=[];position=None
 for i in range(max(entry_n,exit_n),len(rows)-1):
  if position is None and closes[i]>max(closes[i-entry_n:i]): position=(i+1,rows[i+1][1])
  elif position is not None and closes[i]<min(closes[i-exit_n:i]):
   out.append((rows[position[0]][0],rows[i+1][0],position[1],rows[i+1][1]));position=None
 return out
def metrics(values,capital,start,end):
 equity=float(capital);peak=equity;wins=losses=dd=0.;count=0
 for entry_day,exit_day,raw_entry,raw_exit in values:
  if not start<=entry_day<=end or exit_day>end: continue
  entry=raw_entry*1.001;exit_price=raw_exit*.999;shares=math.floor(equity/entry)
  if shares<1: continue
  pnl=shares*(exit_price-entry)-2*max(1,.005*shares);equity+=pnl;peak=max(peak,equity);dd=max(dd,1-equity/peak);wins+=max(pnl,0);losses+=max(-pnl,0);count+=1
 return {'trades':count,'return_pct':(equity/capital-1)*100,'profit_factor':wins/losses if losses else None,'maximum_drawdown_pct':dd*100}
def develop(source):
 spec=json.loads(SPEC.read_text());rows=load(source);periods={k:tuple(map(date.fromisoformat,v)) for k,v in spec['periods'].items() if k!='oos'};points=[];g=spec['gates']
 for entry_n in spec['finite_grid']['entry_lookbacks']:
  for exit_n in spec['finite_grid']['exit_lookbacks']:
   values=trades(rows,entry_n,exit_n);m={stage:{str(cap):metrics(values,cap,*window) for cap in spec['economics']['capitals_usd']} for stage,window in periods.items()};base=[m[x]['500'] for x in ('train','validation')];passed=base[0]['trades']>=g['train_minimum_trades'] and base[1]['trades']>=g['validation_minimum_trades'] and all((x['profit_factor'] or 0)>=g['minimum_profit_factor_each_period'] and x['return_pct']>0 and x['maximum_drawdown_pct']<=g['maximum_drawdown_pct'] for x in base);points.append({'id':f'GLD_BREAKOUT_E{entry_n}_X{exit_n}','entry':entry_n,'exit':exit_n,'metrics':m,'period_pass':passed})
 for p in points:
  neighbors=[x for x in points if abs(spec['finite_grid']['entry_lookbacks'].index(x['entry'])-spec['finite_grid']['entry_lookbacks'].index(p['entry']))+abs(spec['finite_grid']['exit_lookbacks'].index(x['exit'])-spec['finite_grid']['exit_lookbacks'].index(p['exit']))==1];p['profitable_neighbors']=sum(all(x['metrics'][stage]['500']['return_pct']>0 for stage in ('train','validation')) for x in neighbors);p['stable_pass']=p['period_pass'] and p['profitable_neighbors']>=g['minimum_profitable_adjacent_variants']
 stable=[p for p in points if p['stable_pass']];selected=max(stable,key=lambda p:(min(p['metrics'][s]['500']['profit_factor'] for s in ('train','validation')),p['id']))['id'] if stable else None
 return {'schema_version':1,'decision':'PASS_FREEZE_ONE_FOR_OOS' if selected else 'REJECT_DEVELOPMENT','preregistration_sha256':sha(SPEC),'source_sha256':sha(source),'stable_ids':[p['id'] for p in stable],'selected_for_oos':selected,'points':points,'oos_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=develop(a.source);a.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:x[k] for k in ('decision','stable_ids','selected_for_oos')},indent=2))
if __name__=='__main__':main()
