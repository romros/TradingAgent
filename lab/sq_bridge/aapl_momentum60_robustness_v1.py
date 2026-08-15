#!/usr/bin/env python3
"""Deterministic trade-sequence robustness for frozen AAPL Momentum 60."""
from __future__ import annotations
import argparse,json,random
from pathlib import Path

def compounded(values):
 equity=peak=1.;dd=0
 for value in values:equity*=1+value;peak=max(peak,equity);dd=max(dd,1-equity/peak)
 return equity-1,dd
def percentile(values,p):
 values=sorted(values);return values[round((len(values)-1)*p)]
def run(source:Path,runs=10000,seed=20260815):
 x=json.loads(source.read_text());returns=[float(t['net_return']) for t in x['trades']]
 if len(returns)<10:raise ValueError('at least ten completed frozen trades required')
 rng=random.Random(seed);boot=[]
 for _ in range(runs):boot.append(compounded([rng.choice(returns) for _ in returns]))
 loo=[compounded(returns[:i]+returns[i+1:])[0] for i in range(len(returns))]
 observed=compounded(returns);net=observed[0];top3=sum(sorted((max(v,0) for v in returns),reverse=True)[:3])
 result={'schema_version':1,'decision':'PASS_ROBUSTNESS' if sum(r>0 for r,_ in boot)/runs>=.9 and sum(r>0 for r in loo)/len(loo)>=.8 else 'REJECT_ROBUSTNESS','method':'iid_trade_bootstrap_with_replacement_plus_leave_one_out','seed':seed,'runs':runs,'trades':len(returns),'observed_return':net,'observed_max_drawdown':observed[1],'bootstrap_probability_positive':sum(r>0 for r,_ in boot)/runs,'bootstrap_return_p05':percentile([r for r,_ in boot],.05),'bootstrap_return_median':percentile([r for r,_ in boot],.5),'bootstrap_drawdown_p95':percentile([d for _,d in boot],.95),'leave_one_out_positive_ratio':sum(r>0 for r in loo)/len(loo),'leave_one_out_worst_return':min(loo),'top_three_gross_winners_share_of_observed_net':top3/net if net>0 else None,'limitations':['IID bootstrap does not model market-regime clustering.','Ten holdout trades remain a small sample; this is a falsification aid, not proof of future profit.'],'paper_authorized':False,'live_authorized':False}
 return result
def main():
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--output',type=Path,required=True);z=a.parse_args();x=run(z.source);z.output.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
if __name__=='__main__':main()
