#!/usr/bin/env python3
"""Frozen train/validation screen for SPY D1 shock-reversal v1."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path

SPEC=Path(__file__).with_name('spy_d1_shock_reversal_preregistration_v1.json')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
 if '2024' in path.name or '2025' in path.name or '2026' in path.name: raise ValueError('screen source filename must be sealed through 2023')
 rows=[]
 for raw in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not raw or raw[0].lower()=='date': continue
  day=date.fromisoformat(raw[0].replace('.','-'))
  if day>=date(2024,1,1): raise ValueError('OOS row leaked into train/validation screen')
  offset=2 if len(raw)>1 and ':' in raw[1] else 1
  rows.append({'date':day,'open':float(raw[offset]),'close':float(raw[offset+3])})
 if not rows or any(a['date']>=b['date'] for a,b in zip(rows,rows[1:])): raise ValueError('source must be non-empty, unique and ordered')
 return rows
def variants(spec):
 out=[]
 for horizon,key in ((1,'shock_1d_thresholds'),(3,'shock_3d_thresholds')):
  for threshold in spec['finite_grid'][key]:
   for hold in spec['finite_grid']['holding_sessions']:
    out.append({'id':f'SPY_SHOCK_{horizon}D_{abs(round(threshold*1000)):03d}_H{hold}','horizon':horizon,'threshold':threshold,'hold':hold})
 return out
def signals(rows,variant):
 closes=[x['close'] for x in rows];sma=[]
 for i in range(len(rows)): sma.append(sum(closes[i-199:i+1])/200 if i>=199 else None)
 trades=[];last=-1
 for i in range(220,len(rows)-variant['hold']-1):
  if i+1<=last or closes[i]<=sma[i] or sma[i]<=sma[i-20]: continue
  if closes[i]/closes[i-variant['horizon']]-1>variant['threshold']: continue
  entry_i=i+1;exit_i=entry_i+variant['hold'];last=exit_i
  trades.append({'entry':rows[entry_i]['date'],'exit':rows[exit_i]['date'],'entry_price':rows[entry_i]['open'],'exit_price':rows[exit_i]['open']})
 return trades
def metrics(trades,capital,start,end):
 equity=float(capital);peak=equity;wins=losses=dd=0.;used=[]
 for trade in trades:
  if not start<=trade['entry']<=end or trade['exit']>end: continue
  entry=trade['entry_price']*1.001;exit_price=trade['exit_price']*.999;shares=math.floor(equity/entry)
  if shares<1: continue
  pnl=shares*(exit_price-entry)-2*max(1,.005*shares);equity+=pnl;peak=max(peak,equity);dd=max(dd,1-equity/peak);wins+=max(pnl,0);losses+=max(-pnl,0);used.append(pnl)
 return {'trades':len(used),'return_pct':(equity/capital-1)*100,'profit_factor':wins/losses if losses else None,'maximum_drawdown_pct':dd*100,'positive':sum(x>0 for x in used)}
def adjacent(left,right,thresholds,holds):
 if left['horizon']!=right['horizon']: return False
 return abs(thresholds.index(left['threshold'])-thresholds.index(right['threshold']))+abs(holds.index(left['hold'])-holds.index(right['hold']))==1
def run(source):
 spec=json.loads(SPEC.read_text());rows=load(source);points=variants(spec);g=spec['gates'];periods={k:tuple(map(date.fromisoformat,v)) for k,v in spec['periods'].items() if k in {'train','validation'}}
 for point in points:
  all_trades=signals(rows,point);point['metrics']={stage:{str(cap):metrics(all_trades,cap,*window) for cap in spec['economics']['capitals_usd']} for stage,window in periods.items()}
  train=point['metrics']['train']['500'];point['train_pass']=train['trades']>=g['train_minimum_trades'] and (train['profit_factor'] or 0)>=g['train_minimum_stress_profit_factor'] and train['return_pct']>0
 for point in points:
  thresholds=spec['finite_grid']['shock_1d_thresholds' if point['horizon']==1 else 'shock_3d_thresholds'];neighbors=[other for other in points if adjacent(point,other,thresholds,spec['finite_grid']['holding_sessions'])]
  point['profitable_adjacent_train']=sum(other['metrics']['train']['500']['return_pct']>0 and (other['metrics']['train']['500']['profit_factor'] or 0)>=1 for other in neighbors)
  point['stable_train_pass']=point['train_pass'] and point['profitable_adjacent_train']>=g['minimum_profitable_adjacent_variants']
  validation=point['metrics']['validation']['500'];point['validation_pass']=point['stable_train_pass'] and validation['trades']>=g['validation_minimum_trades'] and (validation['profit_factor'] or 0)>=g['validation_minimum_stress_profit_factor'] and validation['return_pct']>0 and validation['maximum_drawdown_pct']<=g['validation_maximum_stress_drawdown_pct']
 passing=[p for p in points if p['validation_pass']]
 selected=max(passing,key=lambda p:(p['metrics']['validation']['500']['profit_factor'],p['metrics']['validation']['500']['return_pct'],p['id']))['id'] if passing else None
 return {'schema_version':1,'decision':'PASS_FREEZE_ONE_FOR_OOS' if selected else 'REJECT_NO_VALIDATED_REGION','preregistration_sha256':sha(SPEC),'source_sha256':sha(source),'source_last_date':rows[-1]['date'].isoformat(),'variants_evaluated':len(points),'stable_train_ids':[p['id'] for p in points if p['stable_train_pass']],'validation_passing_ids':[p['id'] for p in passing],'selected_for_single_oos':selected,'points':points,'oos_accessed':False,'sqcli_started':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=run(a.source);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('decision','stable_train_ids','validation_passing_ids','selected_for_single_oos')},indent=2))
if __name__=='__main__': main()
