#!/usr/bin/env python3
"""Neutral incremental portfolio test for CAT, MSFT and frozen JPM momentum60."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
from three_strategy_portfolio_v1 import load_msft,msft_sleeve
from two_strategy_portfolio_v1 import cat_sleeve,metrics,monthly_correlation

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load_cat(path):
 out=[]
 for row in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not row or row[0].lower()=='date': continue
  day=row[0].replace('-','.');
  if day>='2025.01.01': continue
  off=2 if ':' in row[1] else 1
  out.append({'date':day,'open':float(row[off]),'high':float(row[off+1]),'low':float(row[off+2]),'close':float(row[off+3])})
 return out
def load_jpm(path):
 out=[]
 for row in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not row or row[0].lower()=='date': continue
  day=dt.date.fromisoformat(row[0].replace('.','-'))
  if day.year>=2025: continue
  off=2 if ':' in row[1] else 1
  out.append({'date':day,'open':float(row[off]),'close':float(row[off+3])})
 return out
def jpm_sleeve(rows,capital,start,end):
 a,b=(dt.date.fromisoformat(x.replace('.','-')) for x in (start,end));closes=[x['close'] for x in rows];equity=capital;last=-1;out=[]
 for i in range(60,len(rows)-21):
  if rows[i]['date'].month==rows[i+1]['date'].month or i+1<last or closes[i]<=closes[i-60]: continue
  entry_i=i+1;exit_i=entry_i+20;last=exit_i
  if not a<=rows[entry_i]['date']<=b: continue
  entry=rows[entry_i]['open']*1.001;exit_price=rows[exit_i]['open']*.999;shares=math.floor(equity/entry)
  if shares<1: continue
  pnl=shares*(exit_price-entry)-2*max(1,.005*shares);equity+=pnl
  out.append({'date':rows[exit_i]['date'].isoformat(),'pnl':pnl,'equity':equity,'return':pnl/(equity-pnl)})
 return out
def evaluate(cat,msft,jpm,capital,start,end):
 legs={'CAT_0168':cat_sleeve(cat,capital,start,end),'MSFT_CAPITULATION':msft_sleeve(msft,capital,start,end),'JPM_MOMENTUM60':jpm_sleeve(jpm,capital,start,end)};names=list(legs);pairs={}
 for i,left in enumerate(names):
  for right in names[i+1:]: pairs[f'{left}__{right}']=monthly_correlation(legs[left],legs[right])
 events=[{'date':event['date'],'pnl':event['pnl']} for rows in legs.values() for event in rows]
 return {'strategies':{name:metrics(rows,capital) for name,rows in legs.items()},'portfolio':metrics(events,capital*3),'pairwise_monthly_correlation':pairs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--cat',type=Path,required=True);p.add_argument('--msft',type=Path,required=True);p.add_argument('--jpm',type=Path,required=True);p.add_argument('--capital',type=float,default=1000);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 full=evaluate(load_cat(a.cat),load_msft(a.msft),load_jpm(a.jpm),a.capital,'2019.01.01','2024.12.31');forward=evaluate(load_cat(a.cat),load_msft(a.msft),load_jpm(a.jpm),a.capital,'2022.01.01','2024.12.31')
 correlations=[abs(v['correlation_zero_when_inactive']) for v in forward['pairwise_monthly_correlation'].values() if v['correlation_zero_when_inactive'] is not None];maxcorr=max(correlations,default=1)
 individual=list(forward['strategies'].values());passed=all(x['return_pct']>0 for x in individual) and maxcorr<.5 and forward['portfolio']['max_drawdown_pct_closed_equity']<max(x['max_drawdown_pct_closed_equity'] for x in individual)
 result={'schema_version':1,'classification':'PASS_INCREMENTAL_PORTFOLIO_EDGE' if passed else 'REJECT_PORTFOLIO_COMBINATION','allocation':'three equal independent sleeves; no leverage or weight optimization','full_2019_2024':full,'forward_2022_2024':forward,'maximum_absolute_forward_pairwise_monthly_correlation':maxcorr,'inputs_sha256':{str(x):sha(x) for x in (a.cat,a.msft,a.jpm)},'limitations':['Historical portfolio period is diagnostic, not a new holdout.','Closed-equity drawdown omits intratrade mark-to-market.'],'paper_authorized':False,'live_authorized':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'classification':result['classification'],'forward':forward,'maxcorr':maxcorr},indent=2))
if __name__=='__main__': main()
