#!/usr/bin/env python3
"""Frozen marginal NFLX test against a weight-matched buy-and-hold portfolio."""
from __future__ import annotations
import argparse,json,math,sys
from collections import defaultdict
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from nflx_04681_risk_overlay_v1 import load as load_nflx,commission
from three_edge_vs_weighted_buy_hold_v1 import buy_hold,stats,month_end
from three_strategy_portfolio_v1 import load_msft,msft_sleeve
from two_strategy_portfolio_v1 import load_cat,cat_sleeve,sxr8_sleeve

SPEC=Path(__file__).with_suffix('.json')
def nflx_events(path,capital):
 equity=capital;out=[]
 for r in load_nflx(path):
  if not '2022-01-01'<=r['open_date']<='2024-12-31':continue
  q=math.floor(equity*.75/(r['open']*1.001+commission(1)))
  if q<1:continue
  pnl=q*(r['close']*.999-r['open']*1.001)-2*commission(q);equity+=pnl;out.append({'date':r['close_date'],'pnl':pnl})
 return out
def result(a,nw):
 capital=3000.;remain=100-nw;caps={'SXR8':capital*remain*.4/100,'CAT':capital*remain*.4/100,'MSFT_CAPITULATION':capital*remain*.2/100,'NFLX':capital*nw/100}
 events=sxr8_sleeve(a.sxr8_strategy,caps['SXR8'],'2022.01.01','2024.12.31')+cat_sleeve(load_cat([a.cat_strategy]),caps['CAT'],'2022.01.01','2024.12.31')+msft_sleeve(load_msft(a.msft_strategy),caps['MSFT_CAPITULATION'],'2022.01.01','2024.12.31')+nflx_events(a.nflx_orders,caps['NFLX'])
 pnl=defaultdict(float)
 for x in events:pnl[x['date'][:7]]+=x['pnl']
 eq=capital;active=[]
 for y in range(2022,2025):
  for m in range(1,13):eq+=pnl[f'{y}-{m:02d}'];active.append((date(y,m,28),eq))
 paths={'SXR8':a.sxr8_benchmark,'CAT':a.cat_benchmark,'MSFT_CAPITULATION':a.msft_benchmark,'NFLX':a.nflx_benchmark};costs={'SXR8':(1.25,.0005),'CAT':(1.,.001),'MSFT_CAPITULATION':(1.,.0015),'NFLX':(1.,.001)};legs={k:buy_hold(paths[k],caps[k],*costs[k]) for k in paths};days=sorted(set(d for v in legs.values() for d,_ in v['curve']));series={k:dict(v['curve']) for k,v in legs.items()};last={};bench=[]
 for day in days:
  for k in series:
   if day in series[k]:last[k]=series[k][day]
  if len(last)==4:bench.append((day,sum(last.values())))
 am,bm=stats(active,capital),stats(month_end(bench),capital);raw=am['cagr_pct']>bm['cagr_pct'];risk=am['cagr_pct']>=.75*bm['cagr_pct'] and am['maximum_drawdown_pct_monthly']<=.6*bm['maximum_drawdown_pct_monthly']
 return {'nflx_weight_pct':nw,'capital_by_sleeve':caps,'active':am,'weighted_buy_hold':bm,'comparison':{'cagr_difference_points':am['cagr_pct']-bm['cagr_pct'],'drawdown_ratio':am['maximum_drawdown_pct_monthly']/bm['maximum_drawdown_pct_monthly'],'raw_return_pass':raw,'risk_adjusted_pass':risk},'passes':raw or risk,'events':len(events)}
def main():
 p=argparse.ArgumentParser()
 for n in ('sxr8_benchmark','cat_benchmark','msft_benchmark','nflx_benchmark','sxr8_strategy','cat_strategy','msft_strategy','nflx_orders'):p.add_argument('--'+n.replace('_','-'),dest=n,type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();spec=json.loads(SPEC.read_text());rows=[result(a,w) for w in spec['nflx_weights_pct']];passing=[x for x in rows if x['passes']];selected=max(passing,key=lambda x:x['active']['cagr_pct']/max(x['active']['maximum_drawdown_pct_monthly'],.01)) if passing else None;out={'schema_version':1,'decision':'PASS_ADD_NFLX' if selected else 'FAIL_NFLX_DOES_NOT_CLOSE_BUY_HOLD_GAP','variants':rows,'selected':selected,'weights_were_preregistered':True,'post_2024_accessed':False,'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
