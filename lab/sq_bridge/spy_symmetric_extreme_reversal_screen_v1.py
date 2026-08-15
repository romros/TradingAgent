#!/usr/bin/env python3
"""Development-only screen for preregistered symmetric SPY extremes."""
from __future__ import annotations
import argparse,hashlib,json,math
from datetime import date
from pathlib import Path
from lab.sq_bridge.spy_d1_shock_reversal_screen_v1 import load
SPEC=Path(__file__).with_name('spy_symmetric_extreme_reversal_preregistration_v1.json')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def trades(rows,threshold,hold,side):
 out=[];last=-1
 for i in range(1,len(rows)-hold-1):
  if i+1<=last: continue
  change=rows[i]['close']/rows[i-1]['close']-1;direction='long' if change<=-threshold else 'short' if change>=threshold else None
  if direction is None or side not in {direction,'both'}: continue
  entry=i+1;exit_i=entry+hold;last=exit_i;out.append((rows[entry]['date'],rows[exit_i]['date'],rows[entry]['open'],rows[exit_i]['open'],direction))
 return out
def metrics(values,start,end,capital=1000):
 equity=float(capital);peak=equity;wins=losses=dd=0.;count=0
 for entry_day,exit_day,raw_entry,raw_exit,direction in values:
  if not start<=entry_day<=end or exit_day>end: continue
  shares=math.floor(equity/(raw_entry*1.001));
  if shares<1: continue
  gross=(raw_exit*.999-raw_entry*1.001)*shares if direction=='long' else (raw_entry*.999-raw_exit*1.001)*shares
  pnl=gross-2*max(1,.005*shares);equity+=pnl;peak=max(peak,equity);dd=max(dd,1-equity/peak);wins+=max(pnl,0);losses+=max(-pnl,0);count+=1
 return {'trades':count,'return_pct':(equity/capital-1)*100,'profit_factor':wins/losses if losses else None,'maximum_drawdown_pct':dd*100}
def run(source):
 spec=json.loads(SPEC.read_text());rows=load(source);periods={k:tuple(map(date.fromisoformat,v)) for k,v in spec['development_periods'].items()};points=[];g=spec['gates']
 for threshold in spec['finite_grid']['absolute_thresholds']:
  for hold in spec['finite_grid']['holding_sessions']:
   for side in spec['finite_grid']['sides']:
    values=trades(rows,threshold,hold,side);m={k:metrics(values,*v) for k,v in periods.items()};passed=all(x['trades']>=g['minimum_trades_each_development_period'] and (x['profit_factor'] or 0)>=g['minimum_profit_factor_each_period'] and x['return_pct']>0 and x['maximum_drawdown_pct']<=g['maximum_drawdown_pct'] for x in m.values());points.append({'id':f'SPY_SYM_{round(threshold*1000):03d}_H{hold}_{side.upper()}','threshold':threshold,'hold':hold,'side':side,'metrics':m,'period_pass':passed})
 for point in points:
  adjacent=[x for x in points if x['side']==point['side'] and abs(spec['finite_grid']['absolute_thresholds'].index(x['threshold'])-spec['finite_grid']['absolute_thresholds'].index(point['threshold']))+abs(spec['finite_grid']['holding_sessions'].index(x['hold'])-spec['finite_grid']['holding_sessions'].index(point['hold']))==1]
  point['profitable_neighbors']=sum(all(m['return_pct']>0 for m in x['metrics'].values()) for x in adjacent);point['stable_pass']=point['period_pass'] and point['profitable_neighbors']>=g['minimum_profitable_adjacent_variants']
 stable=[x for x in points if x['stable_pass']];selected=max(stable,key=lambda x:(min(m['profit_factor'] for m in x['metrics'].values()),sum(m['return_pct'] for m in x['metrics'].values()),x['id']))['id'] if stable else None
 return {'schema_version':1,'decision':'PASS_FREEZE_FOR_QQQ_TRANSFER' if selected else 'REJECT_DEVELOPMENT','preregistration_sha256':sha(SPEC),'source_sha256':sha(source),'variants':len(points),'stable_ids':[x['id'] for x in stable],'selected_for_exact_qqq_transfer':selected,'points':points,'spy_oos_accessed':False,'qqq_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();x=run(a.source);a.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:x[k] for k in ('decision','stable_ids','selected_for_exact_qqq_transfer')},indent=2))
if __name__=='__main__': main()
