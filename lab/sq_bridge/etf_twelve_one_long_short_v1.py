#!/usr/bin/env python3
import argparse,datetime as dt,json
from pathlib import Path
from lab.sq_bridge.etf_relative_momentum_screen_v1 import load,reviews,metrics,sha
H=Path(__file__).resolve().parent;S=H/'etf_twelve_one_long_short_preregistration_v1.json';L=H/'etf_twelve_one_long_short_preregistration_v1.lock.json'
def rows(frames,start,end):
 d=sorted(set.intersection(*(set(f) for f in frames.values())));p=reviews(d);out=[]
 for j,s in enumerate(p[:-1]):
  if s<252:continue
  n=p[j+1]
  if n+1>=len(d):continue
  en,ex=d[s+1],d[n+1]
  if not(start<=en and ex<=end):continue
  score={a:f[d[s-21]][1]/f[d[s-252]][1]-1 for a,f in frames.items()};rank=sorted(score,key=lambda a:(score[a],a));lo,hi=rank[0],rank[-1];r=.5*(frames[hi][ex][0]/frames[hi][en][0]-1)+.5*(1-frames[lo][ex][0]/frames[lo][en][0])-.005;out.append({'return':r,'selected':[hi,lo]})
 return out
def run(assets,out):
 s=json.loads(S.read_text());l=json.loads(L.read_text());assert sha(S)==l['preregistration_sha256'];f={k:load(v) for k,v in assets.items()};b={k:tuple(map(dt.date.fromisoformat,v)) for k,v in s['periods'].items()};r={k:metrics(rows(f,*v)) for k,v in b.items()};c=metrics(rows(f,b['validation'][0],b['oos_2024'][1]));g=s['gate'];ok=all(x['total_return']>0 for x in r.values()) and (c['annualized_sharpe'] or -999)>=g['combined_validation_oos_minimum_sharpe'] and c['maximum_drawdown']<=g['combined_maximum_drawdown'];z={'decision':'PASS_EDGE_GATE' if ok else 'REJECT_FAMILY','periods':r,'validation_oos':c,'holdout_2025_plus_accessed':False};out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(z,indent=2)+'\n');return z
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(run({k:Path(v) for k,v in(x.split('=',1) for x in a.asset)},a.output),indent=2))
if __name__=='__main__':main()
