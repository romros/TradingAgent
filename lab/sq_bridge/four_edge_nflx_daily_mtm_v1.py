#!/usr/bin/env python3
"""Synchronize frozen four-edge stress equity with NFLX 0.4681 daily MTM."""
from __future__ import annotations
import argparse,csv,json,math,sys
from bisect import bisect_right
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.five_edge_daily_mtm_v1 import legacy_stress_curve,drawdown
from lab.sq_bridge.nflx_04681_risk_overlay_v1 import load,commission
from lab.sq_bridge.three_edge_vs_weighted_buy_hold_v1 import buy_hold,month_end,stats
from lab.sq_bridge.four_edge_net_mtm_audit_v1 import load_fx,asof

def nflx_curve(orders_path,d1_path):
 prices={}
 with Path(d1_path).open(newline='') as f:
  for r in csv.reader(f):
   d=date.fromisoformat(r[0].replace('.','-'))
   if date(2022,1,1)<=d<=date(2024,12,31):prices[d]=float(r[5])
 orders=[r for r in load(orders_path) if '2022-01-01'<=r['open_date']<='2024-12-31'];calendar=sorted(prices);equity=1000.;position=None;index=0;out=[]
 for day in calendar:
  # SQ can close an existing bracket and create the next stop entry on the same session.
  if position and day==position['close_day']:
   equity=position['cash']+position['q']*position['trade']['close']*.999-commission(position['q']);position=None
  if index<len(orders) and day==date.fromisoformat(orders[index]['open_date']):
   trade=orders[index];index+=1;q=math.floor(equity*.75/(trade['open']*1.001+commission(1)))
   if q>=1:
    cash=equity-q*trade['open']*1.001-commission(q);position={'trade':trade,'q':q,'cash':cash,'close_day':date.fromisoformat(trade['close_date'])}
    if position['close_day']==day:
     equity=cash+q*trade['close']*.999-commission(q);position=None
  value=equity if not position else position['cash']+position['q']*prices[day]*.999-commission(position['q'])
  out.append((day,value))
 return out
def matched_benchmark(a):
 paths={'CAT':a.cat_benchmark,'MSFT':a.msft_benchmark,'JPM':a.jpm_benchmark,'NFLX':a.nflx_benchmark};caps={'CAT':500.,'MSFT':500.,'JPM':500.,'NFLX':1000.};slips={'CAT':.001,'MSFT':.0015,'JPM':.001,'NFLX':.001};legs={k:buy_hold(paths[k],caps[k],1.,slips[k]) for k in paths}
 fx_days,fx_values=load_fx(a.legacy_fx);gold=[]
 with a.sgln_benchmark.open(newline='') as f:
  for r in csv.reader(f):
   day=date.fromisoformat(r[0].replace('.','-'))
   if date(2022,1,1)<=day<=date(2024,12,31):gold.append((day,float(r[2])/100,float(r[5])/100))
 first=gold[0];entry_fx=asof(fx_days,fx_values,first[0]);fee=3*entry_fx;shares=math.floor((500-fee)/(first[1]*entry_fx*1.002));cash=500-shares*first[1]*entry_fx*1.002-fee;gcurve=[]
 for day,_,close in gold:
  fx=asof(fx_days,fx_values,day);gcurve.append((day,cash+shares*close*fx*.998-3*fx))
 series={k:dict(v['curve']) for k,v in legs.items()};series['SGLN']=dict(gcurve);days=sorted(set(d for v in series.values() for d in v));last={};combined=[]
 for day in days:
  for k,v in series.items():
   if day in v:last[k]=v[day]
  if len(last)==5:combined.append((day,sum(last.values())))
 return stats(month_end(combined),3000.)
def evaluate(a):
 legacy=legacy_stress_curve(a.legacy_sqx,a.legacy_fx);nflx=nflx_curve(a.nflx_orders,a.nflx_d1);days=[d for d,_ in nflx];vals=dict(nflx);combined=[]
 for day,old in legacy:
  i=bisect_right(days,day)-1;new=1000. if i<0 else vals[days[i]];combined.append((day,old+new))
 final=combined[-1][1];maximum,pair=drawdown(combined);years=(date(2024,12,31)-date(2022,1,1)).days/365.2425;cagr=((final/3000)**(1/years)-1)*100;spy=json.loads(a.spy_benchmark.read_text())['spy_buy_hold_total_return'];matched=matched_benchmark(a);passed=cagr>spy['cagr_pct'] and maximum<=20
 return {'schema_version':1,'decision':'PASS_FOUR_EDGE_NFLX_BEATS_SPY_BUY_HOLD' if passed else 'FAIL_FOUR_EDGE_NFLX','period':'2022-01-01/2024-12-31','allocation_usd':{'CAT':500,'MSFT':500,'JPM':500,'SGLN':500,'NFLX_04681':1000},'initial_capital_usd':3000,'final_equity_usd':final,'net_return_pct':(final/3000-1)*100,'cagr_pct':cagr,'daily_mtm_max_drawdown_pct':maximum,'drawdown_peak_date':str(pair[0]),'drawdown_trough_date':str(pair[1]),'spy_buy_hold':spy,'matched_assets_buy_hold':matched,'comparison':{'active_minus_spy_cagr_points':cagr-spy['cagr_pct'],'active_minus_spy_return_points':(final/3000-1)*100-spy['net_return_pct'],'active_minus_matched_assets_cagr_points':cagr-matched['cagr_pct'],'drawdown_ratio_vs_spy':maximum/spy['maximum_drawdown_pct'],'beats_spy_raw_return':cagr>spy['cagr_pct'],'beats_matched_assets_raw_return':cagr>matched['cagr_pct'],'risk_gate_pass':maximum<=20},'daily_observations':len(combined),'accounting':'Two fixed sleeves, no transfers: four-edge stress daily MTM + NFLX whole-share 75% exposure daily MTM.','post_2024_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--legacy-sqx',type=Path,required=True);p.add_argument('--legacy-fx',type=Path,required=True);p.add_argument('--nflx-orders',type=Path,required=True);p.add_argument('--nflx-d1',type=Path,required=True);p.add_argument('--spy-benchmark',type=Path,required=True)
 for n in ('cat_benchmark','msft_benchmark','jpm_benchmark','sgln_benchmark','nflx_benchmark'):p.add_argument('--'+n.replace('_','-'),dest=n,type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=evaluate(a);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
