#!/usr/bin/env python3
"""Compare frozen 40/40/20 active sleeves with matching adjusted buy-and-hold."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from collections import defaultdict
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from three_strategy_portfolio_v1 import load_msft,msft_sleeve
from two_strategy_portfolio_v1 import load_cat,cat_sleeve,sxr8_sleeve

START,END=date(2022,1,1),date(2024,12,31)
CAPITALS={'SXR8':1000.,'CAT':1000.,'MSFT_CAPITULATION':500.}
COSTS={'SXR8':(1.25,.0005),'CAT':(1.,.001),'MSFT_CAPITULATION':(1.,.0015)}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prices(path):
 out=[]
 with Path(path).open(newline='') as f:
  for r in csv.DictReader(f):
   d=date.fromisoformat(r['date'])
   if START<=d<=END:out.append((d,float(r['open']),float(r['close'])))
 if not out or out[0][0].year!=2022 or out[-1][0]<date(2024,12,27):raise ValueError(f'incomplete benchmark coverage: {path}')
 return out
def dd(curve):
 peak=curve[0][1];peakday=curve[0][0];worst=0.;pair=(curve[0][0],curve[0][0])
 for d,v in curve:
  if v>peak:peak=v;peakday=d
  now=(peak-v)/peak
  if now>worst:worst=now;pair=(peakday,d)
 return worst*100,pair
def buy_hold(path,capital,fee,slip):
 rows=prices(path);first,last=rows[0],rows[-1];shares=math.floor((capital-fee)/(first[1]*(1+slip)))
 if shares<1:raise ValueError(f'unaffordable benchmark: {path}')
 cash=capital-shares*first[1]*(1+slip)-fee
 curve=[(d,cash+shares*c*(1-slip)-fee) for d,_,c in rows]
 final=curve[-1][1];draw,pair=dd(curve)
 return {'initial_capital':capital,'shares':shares,'cash':cash,'first_session':first[0].isoformat(),'last_session':last[0].isoformat(),'final_equity':final,'return_pct':(final/capital-1)*100,'maximum_drawdown_pct_daily':draw,'drawdown_peak':pair[0].isoformat(),'drawdown_trough':pair[1].isoformat(),'curve':curve}
def active_events(sxr8,cat,msft):
 cr=load_cat([cat]);mr=load_msft(msft)
 return sxr8_sleeve(sxr8,1000.,'2022.01.01','2024.12.31')+cat_sleeve(cr,1000.,'2022.01.01','2024.12.31')+msft_sleeve(mr,500.,'2022.01.01','2024.12.31')
def month_end(curve):
 out={}
 for d,v in sorted(curve):out[d.strftime('%Y-%m')]=(d,v)
 return [out[k] for k in sorted(out)]
def stats(curve,initial):
 final=curve[-1][1];years=(END-START).days/365.2425;draw,pair=dd(curve)
 return {'initial_capital':initial,'final_equity':final,'return_pct':(final/initial-1)*100,'cagr_pct':((final/initial)**(1/years)-1)*100,'maximum_drawdown_pct_monthly':draw,'drawdown_peak':pair[0].isoformat(),'drawdown_trough':pair[1].isoformat()}
def run(a):
 paths={'SXR8':a.sxr8_benchmark,'CAT':a.cat_benchmark,'MSFT_CAPITULATION':a.msft_benchmark};legs={k:buy_hold(paths[k],CAPITALS[k],*COSTS[k]) for k in paths}
 days=sorted(set(d for leg in legs.values() for d,_ in leg['curve']));values={k:dict(v['curve']) for k,v in legs.items()};last={};combined=[]
 for day in days:
  for k in values:
   if day in values[k]:last[k]=values[k][day]
  if len(last)==3:combined.append((day,sum(last.values())))
 events=active_events(a.sxr8_strategy,a.cat_strategy,a.msft_strategy);monthly=defaultdict(float)
 for x in events:monthly[x['date'][:7]]+=x['pnl']
 equity=sum(CAPITALS.values());active=[]
 for y in range(2022,2025):
  for m in range(1,13):
   equity+=monthly[f'{y}-{m:02d}'];active.append((date(y,m,28),equity))
 am,bm=stats(active,2500.),stats(month_end(combined),2500.)
 raw=am['cagr_pct']>bm['cagr_pct'];risk=am['cagr_pct']>=.75*bm['cagr_pct'] and am['maximum_drawdown_pct_monthly']<=.60*bm['maximum_drawdown_pct_monthly']
 return {'schema_version':1,'decision':'PASS_ACTIVE_BEATS_BUY_HOLD' if raw else ('PASS_RISK_ADJUSTED_UTILITY' if risk else 'FAIL_ACTIVE_BELOW_BUY_HOLD'),'period':'2022-01-01/2024-12-31','allocation_pct':{'SXR8':40,'CAT':40,'MSFT_CAPITULATION':20},'capital':2500,'active':am,'weighted_buy_hold':bm,'buy_hold_legs':{k:{x:y for x,y in v.items() if x!='curve'} for k,v in legs.items()},'comparison':{'active_minus_buy_hold_cagr_points':am['cagr_pct']-bm['cagr_pct'],'active_to_buy_hold_monthly_drawdown_ratio':am['maximum_drawdown_pct_monthly']/bm['maximum_drawdown_pct_monthly'],'raw_return_pass':raw,'risk_adjusted_pass':risk},'methodology':'Whole shares; frozen 40/40/20 sleeves; adjusted prices; entry and terminal-exit costs; monthly common observation for drawdown. No rebalancing.','limitations':['Active monthly closed equity omits intratrade drawdown','Mixed EUR/USD sleeves are accounting units; FX conversion excluded'],'inputs_sha256':{str(p):sha(p) for p in paths.values()},'post_2024_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser()
 for n in ('sxr8_benchmark','cat_benchmark','msft_benchmark','sxr8_strategy','cat_strategy','msft_strategy'):p.add_argument('--'+n.replace('_','-'),dest=n,type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=run(a);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
