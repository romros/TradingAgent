#!/usr/bin/env python3
"""Neutral CAT + MSFT + AAPL consolidated-edge portfolio audit."""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
from three_strategy_portfolio_v1 import load_msft,msft_sleeve
from two_strategy_portfolio_v1 import cat_sleeve,metrics,monthly_correlation
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_cat_through_2024(path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for row in csv.reader(f):
   if not row or row[0].lower()=='date':continue
   day=row[0].replace('-','.');
   if day>='2025.01.01':continue
   off=2 if ':' in row[1] else 1;out.append({'date':day,'open':float(row[off]),'high':float(row[off+1]),'low':float(row[off+2]),'close':float(row[off+3])})
 return out
def load_aapl(path):
 out=[]
 for x in csv.reader(path.open(newline='',encoding='utf-8-sig')):
  if not x or x[0].lower()=='date':continue
  d=dt.date.fromisoformat(x[0].replace('.','-'))
  if d.year>=2025:raise ValueError('post-2024 AAPL sealed for historical portfolio audit')
  off=2 if '.' in x[0] else 1;out.append({'date':d,'open':float(x[off]),'close':float(x[off+3])})
 return out
def aapl_sleeve(rows,capital,start,end):
 a,b=map(lambda x:dt.date.fromisoformat(x.replace('.','-')),(start,end));c=[x['close'] for x in rows];equity=capital;last=-1;out=[]
 for i in range(60,len(rows)-22):
  if rows[i]['date'].month==rows[i+1]['date'].month or i+1<last or c[i]<=c[i-60]:continue
  en=i+1;ex=en+20;last=ex
  if not a<=rows[en]['date']<=b:continue
  entry=rows[en]['open']*1.001;exitp=rows[ex]['open']*.999;shares=math.floor(equity/entry)
  if shares<1:continue
  pnl=shares*(exitp-entry)-2*max(1,.005*shares);equity+=pnl;out.append({'date':rows[ex]['date'].isoformat(),'pnl':pnl,'equity':equity,'return':pnl/(equity-pnl)})
 return out
def period(cat,msft,aapl,capital,start,end):
 legs={'CAT_0168':cat_sleeve(cat,capital,start,end),'MSFT_CAPITULATION':msft_sleeve(msft,capital,start,end),'AAPL_MOMENTUM60':aapl_sleeve(aapl,capital,start,end)};names=list(legs);pairs={}
 for i,x in enumerate(names):
  for y in names[i+1:]:pairs[f'{x}__{y}']=monthly_correlation(legs[x],legs[y])
 events=[{'date':e['date'],'pnl':e['pnl']} for rows in legs.values() for e in rows]
 return {'strategies':{k:metrics(v,capital) for k,v in legs.items()},'portfolio':metrics(events,capital*3),'pairwise_monthly_correlation':pairs}
def main():
 p=argparse.ArgumentParser();p.add_argument('--cat',type=Path,required=True);p.add_argument('--msft',type=Path,required=True);p.add_argument('--aapl',type=Path,required=True);p.add_argument('--capital',type=float,default=1000);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cat=load_cat_through_2024(a.cat);msft=load_msft(a.msft);aapl=load_aapl(a.aapl)
 full=period(cat,msft,aapl,a.capital,'2019.01.01','2024.12.31');forward=period(cat,msft,aapl,a.capital,'2022.01.01','2024.12.31');maxcorr=max(abs(v['correlation_zero_when_inactive']) for v in forward['pairwise_monthly_correlation'].values() if v['correlation_zero_when_inactive'] is not None);passed=all(v['return_pct']>0 for v in forward['strategies'].values()) and maxcorr<.5 and forward['portfolio']['max_drawdown_pct_closed_equity']<max(v['max_drawdown_pct_closed_equity'] for v in forward['strategies'].values())
 out={'schema_version':1,'classification':'PASS_THREE_CONSOLIDATED_EDGE_PORTFOLIO' if passed else 'REJECT_PORTFOLIO_COMBINATION','allocation':'three equal independent sleeves; no leverage, transfer or weight optimization','costs':'IBKR-like whole shares, USD1/order minimum and 10bps adverse slippage each side for CAT/AAPL; MSFT frozen 30bps','full_2019_2024':full,'forward_2022_2024':forward,'maximum_absolute_forward_pairwise_monthly_correlation':maxcorr,'inputs_sha256':{str(x):sha(x) for x in (a.cat,a.msft,a.aapl)},'limitations':['Historical portfolio period helped form parts of the hypotheses and is not a new holdout.','Closed-equity drawdown omits intratrade mark-to-market.'],'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'classification':out['classification'],'forward':forward,'maxcorr':maxcorr},indent=2))
if __name__=='__main__':main()
