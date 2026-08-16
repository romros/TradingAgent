#!/usr/bin/env python3
"""Recommend capital separately for raw outperformance and defensive utility."""
from __future__ import annotations
import argparse,json,math
from datetime import datetime
from pathlib import Path
from lab.sq_bridge.five_edge_vs_buy_hold_v1 import ROOT,adjusted_rows,dd,raw_rows

def benchmark(spec,capital,start,end):
 b=spec['benchmark'];raw=[r for r in raw_rows(ROOT/b['raw_price_data']) if start<=r['date']<=end];adj=[r for r in adjusted_rows(ROOT/b['dividend_adjusted_total_return_data']) if start<=r['date']<=end];slip=b['slippage_bps_per_side']/10000;commission=b['commission_usd_per_order'];price=float(raw[0]['open']);shares=math.floor((capital-2*commission)/(price*(1+2*slip)));notional=shares*price;cash=capital-notional-2*commission-2*notional*slip;curve=[(r['date'],cash+notional*r['close']/adj[0]['open']) for r in adj];maximum,_=dd(curve);years=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days/365.2425;ret=(curve[-1][1]/capital-1)*100;cagr=((curve[-1][1]/capital)**(1/years)-1)*100;return {'net_return_pct':ret,'cagr_pct':cagr,'maximum_drawdown_pct':maximum,'shares':shares}
def evaluate(spec_path):
 spec=json.loads(spec_path.read_text());start,end=spec['period'];inputs=spec['inputs'];multi=json.loads((ROOT/inputs['multi_asset']).read_text())['results']['1000']['common_2022_2024'];legacy=json.loads((ROOT/inputs['legacy_four']).read_text())['scenarios']['stress'];five=json.loads((ROOT/inputs['five_edge']).read_text());years=(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days/365.2425
 active={1000:{'net_return_pct':multi['return_pct'],'maximum_drawdown_pct':multi['maximum_mark_to_market_drawdown_pct']},2000:{'net_return_pct':legacy['net_return_pct'],'maximum_drawdown_pct':legacy['daily_mtm_max_drawdown_pct']},3000:{'net_return_pct':five['net_return_pct'],'maximum_drawdown_pct':five['daily_mtm_max_drawdown_pct']}}
 bench_spec=json.loads((ROOT/inputs['benchmark_spec']).read_text());rows={}
 for capital,a in active.items():
  a['cagr_pct']=((1+a['net_return_pct']/100)**(1/years)-1)*100;b=benchmark(bench_spec,capital,start,end);raw=a['cagr_pct']>b['cagr_pct'];defensive=a['cagr_pct']>=.75*b['cagr_pct'] and a['maximum_drawdown_pct']<=.60*b['maximum_drawdown_pct'];rows[str(capital)]={'active':a,'spy_buy_hold':b,'raw_return_win':raw,'defensive_utility_pass':defensive}
 raw_levels=[int(k) for k,v in rows.items() if v['raw_return_win']];defensive_levels=[int(k) for k,v in rows.items() if v['defensive_utility_pass']]
 return {'schema_version':1,'decision':'ACTIVE_RAW_OUTPERFORMANCE_FOUND' if raw_levels else 'NO_ACTIVE_RAW_OUTPERFORMANCE_YET','period':f'{start}/{end}','levels':rows,'recommended_capital_for_raw_outperformance_usd':min(raw_levels) if raw_levels else None,'recommended_capital_for_defensive_utility_usd':min(defensive_levels) if defensive_levels else None,'interpretation':'Defensive utility is not raw-return outperformance and does not complete the primary research objective.','paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=evaluate(a.spec);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
