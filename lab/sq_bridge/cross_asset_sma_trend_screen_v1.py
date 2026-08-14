#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from lab.sq_bridge.equity_momentum_portfolio_v1 import load,metrics,rebalance_indices,sha
HERE=Path(__file__).resolve().parent; SPEC=HERE/'cross_asset_sma_trend_preregistration_v1.json'; LOCK=HERE/'cross_asset_sma_trend_preregistration_v1.lock.json'
def run(frames,kind,start,end):
 d=sorted(set.intersection(*(set(x) for x in frames.values()))); pts=rebalance_indices(d,'monthly_last_session'); out=[]; turn=0; old={a:0 for a in frames}
 for si in pts:
  ei=si+1; xi=min(next((x for x in pts if x>si),len(d)-1)+1,len(d)-1)
  if si<200 or ei>=len(d) or xi<=ei or not(start<=d[ei] and d[xi]<=end):continue
  want={}
  for a,f in frames.items():
   c=[f[d[j]][1] for j in range(si-199,si+1)]; sma200=sum(c)/200
   want[a]=int(f[d[si]][1]>sma200) if kind=='price_sma200' else int(sum(c[-50:])/50>sma200)
  turn+=sum(abs(want[a]-old[a]) for a in frames)/len(frames);old=want
  out.append((d[xi],sum(want[a]*(frames[a][d[xi]][0]/frames[a][d[ei]][0]-1) for a in frames)/len(frames)))
 return {'metrics':metrics(out),'turnover_one_way':turn}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
 src=dict(x.split('=',1) for x in a.asset)
 if set(src)!=set(spec['assets']):raise SystemExit('frozen universe required')
 frames={k:load(Path(v)) for k,v in src.items()};r={'schema_version':1,'preregistration_sha256':sha(SPEC),'periods':{},'holdout_2025_accessed':False,'optimized':False}
 for p,b in spec['periods'].items():
  if p!='holdout_2025':r['periods'][p]={v['id']:run(frames,v['id'],*b) for v in spec['variants']}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r['periods'],indent=2))
if __name__=='__main__':main()
