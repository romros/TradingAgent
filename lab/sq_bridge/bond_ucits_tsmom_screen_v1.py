#!/usr/bin/env python3
"""Frozen 12-month long/cash momentum transfer across two Treasury UCITS ETFs."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load
H=Path(__file__).resolve().parent;S=H/'bond_ucits_tsmom_preregistration_v1.json';L=H/'bond_ucits_tsmom_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def monthly(f,cost):
 months={}
 for d in sorted(f):months.setdefault((d.year,d.month),[]).append(d)
 keys=sorted(months);out=[];old=0
 for i in range(12,len(keys)-1):
  if i+1>=len(keys):break
  signal=months[keys[i]][-1];past=months[keys[i-12]][-1];entry=months[keys[i+1]][0]
  if i+2>=len(keys):break
  exit_=months[keys[i+2]][0];pos=int(f[signal][1]>f[past][1]);turn=abs(pos-old)
  out.append((entry,exit_,pos*(f[exit_][0]/f[entry][0]-1)-turn*cost,pos,turn));old=pos
 return out
def period(rows,a,b):return [x for x in rows if a<=x[0] and x[1]<=b]
def metrics(rows):
 rs=[x[2] for x in rows];n=len(rs)
 if not n:return {'months':0}
 mean=sum(rs)/n;sd=(sum((x-mean)**2 for x in rs)/(n-1))**.5 if n>1 else 0;eq=peak=1.;dd=0.
 for r in rs:eq*=1+r;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'months':n,'invested_months':sum(x[3] for x in rows),'position_changes':sum(x[4] for x in rows),'total_return':eq-1,'annualized_return':eq**(12/n)-1,'annualized_sharpe':mean/sd*math.sqrt(12) if sd else None,'max_drawdown':dd}
def corr(a,b):
 x={r[0]:r[2] for r in a};y={r[0]:r[2] for r in b};ks=sorted(set(x)&set(y))
 if len(ks)<2:return {'months':len(ks),'correlation':None}
 mx=sum(x[k] for k in ks)/len(ks);my=sum(y[k] for k in ks)/len(ks);den=(sum((x[k]-mx)**2 for k in ks)*sum((y[k]-my)**2 for k in ks))**.5
 return {'months':len(ks),'correlation':sum((x[k]-mx)*(y[k]-my) for k in ks)/den if den else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());lock=json.loads(L.read_text());h=sha(S)
 if h!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
 paths=dict(x.split('=',1) for x in a.asset);expected={x['id'] for x in s['instruments']}
 if set(paths)!=expected:raise ValueError('exact frozen instruments required')
 frames={k:load(Path(v)) for k,v in paths.items()};costs={'gross':0.,'tiered':s['economics']['tiered_cost_each_position_change']/1000,'stress':s['economics']['stress_cost_each_position_change']/1000};raw={};report={'schema_version':1,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'assets':{}}
 gates=s['gates'];passes={}
 for asset,frame in frames.items():
  raw[asset]={name:monthly(frame,cost) for name,cost in costs.items()};report['assets'][asset]={'source_sha256':sha(paths[asset]),'costs':{}}
  for plan,rows in raw[asset].items():
   report['assets'][asset]['costs'][plan]={p:metrics(period(rows,*map(dt.date.fromisoformat,b))) for p,b in s['periods'].items() if p!='holdout'}
   report['assets'][asset]['costs'][plan]['combined_validation_oos']=metrics(period(rows,dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1])))
  m=report['assets'][asset]['costs']['stress'];c=m['combined_validation_oos'];passes[asset]=(m['train']['months']>=gates['train_min_months'] and m['validation']['months']>=gates['validation_min_months'] and m['oos']['months']>=gates['oos_min_months'] and all(m[p]['total_return']>0 for p in ('train','validation','oos')) and (c['annualized_sharpe'] or -999)>=gates['combined_validation_oos_stress_sharpe_gte'] and c['max_drawdown']<=gates['combined_validation_oos_stress_max_drawdown_lte'])
 lo,hi=dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1]);co=corr(period(raw['IBTM_L']['stress'],lo,hi),period(raw['IDTL_L']['stress'],lo,hi));passed=all(passes.values()) and (co['correlation'] or -1)>=gates['monthly_return_correlation_gte'];report['decision']={'status':'PASS_THIRD_EDGE_CANDIDATE' if passed else 'REJECT_BOND_TSMOM_TRANSFER','asset_pass':passes,'transfer_correlation':co,'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['decision'],indent=2))
if __name__=='__main__':main()
