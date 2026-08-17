#!/usr/bin/env python3
"""Frozen standalone 12-month time-series momentum screen on IDTL."""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from datetime import date
from pathlib import Path

EXPECTED="3bf1c6020b2d32233ba393e0880d9f220c54afa4def35a8eb7f5d2d5ce04cd4e"
PERIODS={'train':(date(2016,1,1),date(2021,12,31)),'validation':(date(2022,1,1),date(2023,12,31)),'oos':(date(2024,1,1),date(2024,12,31)),'combined':(date(2022,1,1),date(2024,12,31))}
COST=.003+.001
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 out={}
 with Path(p).open(newline='') as f:
  for r in csv.reader(f):out[date.fromisoformat(r[0].replace('.','-'))]=(float(r[2]),float(r[5]))
 return out
def rows(prices):
 months={}
 for d in sorted(prices):months.setdefault((d.year,d.month),[]).append(d)
 keys=sorted(months);out=[];old=0
 for i in range(12,len(keys)-1):
  nxt=keys[i+1];after=keys[i+2] if i+2<len(keys) else None
  if nxt[0]*12+nxt[1]!=keys[i][0]*12+keys[i][1]+1 or after is None or after[0]*12+after[1]!=nxt[0]*12+nxt[1]+1:continue
  signal=months[keys[i]][-1];entry=months[nxt][0];exit_=months[after][0];pos=int(prices[signal][1]>prices[months[keys[i-12]][-1]][1]);turn=abs(pos-old)
  out.append((entry,pos*(prices[exit_][0]/prices[entry][0]-1)-turn*COST,pos,turn));old=pos
 return out
def metrics(xs):
 rs=[x[1] for x in xs];eq=peak=1.;dd=0.
 for r in rs:eq*=1+r;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 mean=sum(rs)/len(rs);sd=math.sqrt(sum((r-mean)**2 for r in rs)/(len(rs)-1)) if len(rs)>1 else 0
 return {'months':len(rs),'invested_months':sum(x[2] for x in xs),'position_changes':sum(x[3] for x in xs),'total_return':eq-1,'annualized_return':eq**(12/len(rs))-1,'annualized_sharpe':mean/sd*math.sqrt(12) if sd else None,'maximum_drawdown':dd}
def run(path):
 if sha(path)!=EXPECTED:raise ValueError('frozen IDTL hash mismatch')
 allrows=rows(load(path));result={k:metrics([x for x in allrows if a<=x[0]<=b]) for k,(a,b) in PERIODS.items()};c=result['combined']
 passed=all(result[k]['total_return']>0 for k in ('train','validation','oos')) and c['annualized_sharpe']>=.4 and c['maximum_drawdown']<=.2 and c['invested_months']>=12
 return {'schema_version':1,'decision':'PASS_IDTL_TSMOM12_EDGE' if passed else 'REJECT_IDTL_TSMOM12','source_sha256':sha(path),'economics':{'cost_each_position_change_fraction':COST},'periods':result,'optimized':False,'post_2024_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('data',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.data);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
