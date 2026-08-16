#!/usr/bin/env python3
"""Post-OOS block-bootstrap audit of the frozen multi-asset edge."""
from __future__ import annotations
import argparse,calendar,json,random,statistics
from pathlib import Path
from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import ROOT,load,simulate

VARIANT={'family':'trend_pullback','sma':200,'down_days':3,'hold_days':10}
def months(start_year,end_year):return [f'{year:04d}-{month:02d}' for year in range(start_year,end_year+1) for month in range(1,13)]
def percentile(values,p):
 ordered=sorted(values);position=(len(ordered)-1)*p;left=int(position);fraction=position-left
 return ordered[left]*(1-fraction)+ordered[min(left+1,len(ordered)-1)]*fraction
def audit(spec_path:Path,simulations=10000,seed=20260816):
 spec=json.loads(spec_path.read_text());econ=spec['economics'];timeline=months(2022,2024);monthly={month:0. for month in timeline}
 for path in spec['assets'].values():
  for trade in simulate(load(ROOT/path),VARIANT,econ):
   month=trade['exit'][:7]
   if month in monthly and trade['entry']>='2022-01-01':monthly[month]+=trade['pnl']/len(spec['assets'])/econ['capital_usd']
 values=[monthly[key] for key in timeline];blocks=[values[index:index+3] for index in range(0,len(values),3)];rng=random.Random(seed);samples=[]
 for _ in range(simulations):samples.append(sum(value for _ in range(len(blocks)) for value in blocks[rng.randrange(len(blocks))]))
 signs=[]
 for _ in range(simulations):signs.append(sum(value if rng.random()<.5 else -value for value in values))
 observed=sum(values);p_value=(1+sum(value>=observed for value in signs))/(simulations+1);probability=sum(value>0 for value in samples)/simulations
 checks={'bootstrap_probability_positive':probability>=.95,'bootstrap_p05_positive':percentile(samples,.05)>0,'sign_flip_p_value':p_value<=.05}
 return {'schema_version':1,'decision':'PASS_POST_OOS_ROBUSTNESS' if all(checks.values()) else 'FAIL_POST_OOS_ROBUSTNESS','variant':VARIANT,'period':'2022-01..2024-12','monthly_observations':len(values),'block_months':3,'simulations':simulations,'seed':seed,'observed_additive_return':observed,'positive_month_fraction':sum(value>0 for value in values)/len(values),'bootstrap_probability_positive':probability,'bootstrap_total_return_p05':percentile(samples,.05),'bootstrap_total_return_p50':percentile(samples,.5),'bootstrap_total_return_p95':percentile(samples,.95),'one_sided_sign_flip_p_value':p_value,'checks':checks,'parameter_selection_performed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.spec);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
