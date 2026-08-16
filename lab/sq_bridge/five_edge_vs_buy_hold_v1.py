#!/usr/bin/env python3
"""Frozen same-capital comparison of the five-edge baseline and SPY buy/hold."""
from __future__ import annotations
import argparse,csv,json,math
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def raw_rows(path):
 with path.open(newline='') as s:return list(csv.DictReader(s))
def adjusted_rows(path):
 rows=[]
 with path.open(newline='') as s:
  for r in csv.reader(s):
   rows.append({'date':datetime.strptime(r[0],'%Y.%m.%d').date().isoformat(),'open':float(r[2]),'close':float(r[5])})
 return rows
def dd(values):
 peak=values[0][1];peak_day=values[0][0];maximum=0;pair=(peak_day,peak_day)
 for day,value in values:
  if value>peak:peak=value;peak_day=day
  draw=(peak-value)/peak*100
  if draw>maximum:maximum=draw;pair=(peak_day,day)
 return maximum,pair
def evaluate(spec_path):
 spec=json.loads(spec_path.read_text());start,end=spec['period'];b=spec['benchmark'];capital=spec['capital_usd']
 raw=[r for r in raw_rows(ROOT/b['raw_price_data']) if start<=r['date']<=end];adj=[r for r in adjusted_rows(ROOT/b['dividend_adjusted_total_return_data']) if start<=r['date']<=end]
 if not raw or not adj or raw[0]['date']!=adj[0]['date'] or raw[-1]['date']!=adj[-1]['date']:raise ValueError('benchmark date coverage mismatch')
 slip=b['slippage_bps_per_side']/10000;commission=b['commission_usd_per_order'];raw_entry=float(raw[0]['open'])
 shares=math.floor((capital-2*commission)/(raw_entry*(1+2*slip)))
 if shares<1:raise ValueError('benchmark unaffordable')
 entry_notional=shares*raw_entry;cash=capital-entry_notional-2*commission-2*entry_notional*slip
 adj_entry=adj[0]['open'];curve=[]
 for r in adj:curve.append((r['date'],cash+entry_notional*(r['close']/adj_entry)))
 benchmark_final=curve[-1][1];benchmark_return=(benchmark_final/capital-1)*100;years=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days/365.2425;benchmark_cagr=((benchmark_final/capital)**(1/years)-1)*100;benchmark_dd,pair=dd(curve)
 active=json.loads((ROOT/spec['active_result']).read_text());active_return=active['net_return_pct'];active_cagr=((1+active_return/100)**(1/years)-1)*100;active_dd=active['daily_mtm_max_drawdown_pct']
 return_pass=active_cagr>benchmark_cagr;risk_pass=active_cagr>=.75*benchmark_cagr and active_dd<=.60*benchmark_dd;passed=return_pass or risk_pass
 return {'schema_version':1,'decision':'PASS_ACTIVE_JUSTIFIES_COMPLEXITY' if passed else 'FAIL_ACTIVE_BELOW_BUY_HOLD_OBJECTIVE','period':f'{start}/{end}','capital_usd':capital,'active':{'net_return_pct':active_return,'cagr_pct':active_cagr,'maximum_drawdown_pct':active_dd},'spy_buy_hold_total_return':{'shares':shares,'cash_usd':cash,'net_return_pct':benchmark_return,'cagr_pct':benchmark_cagr,'maximum_drawdown_pct':benchmark_dd,'drawdown_peak_date':pair[0],'drawdown_trough_date':pair[1]},'comparison':{'active_minus_benchmark_return_points':active_return-benchmark_return,'active_minus_benchmark_cagr_points':active_cagr-benchmark_cagr,'drawdown_ratio_active_to_benchmark':active_dd/benchmark_dd,'return_pass':return_pass,'risk_adjusted_pass':risk_pass},'benchmark_role':'comparison_only_not_strategy_candidate','paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=evaluate(a.spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
