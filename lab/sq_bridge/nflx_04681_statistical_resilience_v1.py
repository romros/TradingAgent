#!/usr/bin/env python3
"""Preregistered account-size-independent resilience screen for NFLX 0.4681."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, random
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=HERE/'nflx_04681_statistical_resilience_preregistration_v1.json'
LOCK=HERE/'nflx_04681_statistical_resilience_preregistration_v1.lock.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pf(xs):
 g=sum(x for x in xs if x>0); loss=-sum(x for x in xs if x<0)
 return math.inf if loss==0 and g>0 else (g/loss if loss else 0.0)
def compounded(xs):
 out=1.0
 for x in xs: out*=1+x
 return out-1
def pct(values,q):
 x=sorted(values); pos=(len(x)-1)*q; lo=int(pos); hi=min(lo+1,len(x)-1)
 return x[lo]+(x[hi]-x[lo])*(pos-lo)
def load(path,bps):
 with Path(path).open(newline='',encoding='utf-8-sig') as f:
  rows=[r for r in csv.DictReader(f,delimiter=';') if r['Type']=='Buy']
 cost=bps/10000
 return [{'year':int(r['Open time'][:4]),'ticket':r['Ticket'],
          'ret':float(r['Close price'])/float(r['Open price'])-1-cost} for r in rows]
def main():
 a=argparse.ArgumentParser();a.add_argument('--orders',type=Path,required=True);a.add_argument('--output',type=Path,required=True);z=a.parse_args()
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256']:raise ValueError('preregistration hash mismatch')
 if sha(z.orders)!=spec['input_orders_sha256']:raise ValueError('orders hash mismatch')
 sets={str(b):load(z.orders,b) for b in spec['frozen_costs']['round_trip_bps']}
 def metrics(rows):
  xs=[r['ret'] for r in rows];return {'trades':len(xs),'compounded_return':compounded(xs),'profit_factor':pf(xs),'mean_return':sum(xs)/len(xs)}
 stress=metrics(sets['100']); base=sets['50']; winners=sorted(base,key=lambda r:r['ret'],reverse=True)
 removed=metrics(winners[3:]); regimes={k:metrics([r for r in base if lo<=r['year']<=hi]) for k,lo,hi in [('2017-2020',2017,2020),('2021-2024',2021,2024)]}
 gains=sum(max(0,r['ret']) for r in base); concentration=sum(r['ret'] for r in winners[:3])/gains
 by_year={y:[r['ret'] for r in base if r['year']==y] for y in range(2017,2025)}; rng=random.Random(4681); boots=[]
 for _ in range(20000):
  sample=[]
  for _ in range(8):sample.extend(by_year[rng.randint(2017,2024)])
  boots.append(compounded(sample))
 bootstrap={'attempts':len(boots),'probability_positive':sum(x>0 for x in boots)/len(boots),'fifth_percentile':pct(boots,.05),'median':pct(boots,.5)}
 checks={'stress_100bps':stress['compounded_return']>0 and stress['profit_factor']>=1.2,
         'remove_top_three_winners_at_50bps':removed['compounded_return']>0 and removed['profit_factor']>=1.1,
         'two_regimes_at_50bps':all(x['compounded_return']>0 and x['profit_factor']>=1.1 for x in regimes.values()),
         'winner_concentration_at_50bps':concentration<=.5,
         'annual_block_bootstrap_at_50bps':bootstrap['probability_positive']>=.9 and bootstrap['fifth_percentile']>=-.15}
 out={'schema_version':1,'decision':'PASS_CENTRAL_STATISTICAL_RESILIENCE' if all(checks.values()) else 'FAIL_CENTRAL_STATISTICAL_RESILIENCE','candidate':spec['candidate'],'checks':checks,'cost_scenarios':{k:metrics(v) for k,v in sets.items()},'remove_top_three':removed,'removed_tickets':[r['ticket'] for r in winners[:3]],'regimes':regimes,'top_three_positive_gain_share':concentration,'annual_block_bootstrap':bootstrap,'does_not_override_parameter_neighborhood_gate':True,'holdout_2025_accessed':False,'paper_authorized':False,'live_authorized':False}
 z.output.parent.mkdir(parents=True,exist_ok=True);z.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
