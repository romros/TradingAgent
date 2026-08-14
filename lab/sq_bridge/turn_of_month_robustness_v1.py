#!/usr/bin/env python3
import argparse,datetime as dt,hashlib,json,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load,metrics
H=Path(__file__).resolve().parent;S=H/'turn_of_month_robustness_preregistration_v1.json';L=H/'turn_of_month_robustness_preregistration_v1.lock.json'
def window(f,start,end,eo,xd):
 ds=sorted(f);m={}
 for d in ds:m.setdefault((d.year,d.month),[]).append(d)
 ks=sorted(m);z=[]
 for i in range(len(ks)-1):
  a,b=ks[i],ks[i+1]
  if b[0]*12+b[1]!=a[0]*12+a[1]+1 or len(m[b])<xd:continue
  j=len(m[a])-1+eo
  if not 0<=j<len(m[a]):
   if eo==1 and i+1<len(ks):entry=m[b][0]
   else:continue
  else:entry=m[a][j]
  exit_=m[b][xd-1]
  if entry>=exit_ or not(start<=entry and exit_<=end):continue
  z.append((exit_,f[exit_][0]/f[entry][0]-1))
 return z
def bootstrap(rows,n,seed):
 by={}
 for d,r in rows:by.setdefault(d.year,[]).append(r)
 years=sorted(by);rng=random.Random(seed);means=[]
 for _ in range(n):
  vals=[r for y in rng.choices(years,k=len(years)) for r in by[y]];means.append(sum(vals)/len(vals))
 means.sort();return {'iterations':n,'probability_mean_positive':sum(x>0 for x in means)/n,'mean_ci_2_5':means[int(.025*n)],'mean_ci_97_5':means[int(.975*n)-1]}
ap=argparse.ArgumentParser();ap.add_argument('--spy',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
f=load(a.spy);full=(dt.date(2017,1,1),dt.date(2024,12,31));vo=(dt.date(2022,1,1),dt.date(2024,12,31));base=window(f,*full,0,4);neighbors=[]
for x in s['diagnostics']['neighbor_windows']:
 q={**x,'full':metrics(window(f,*full,x['entry_from_month_end'],x['exit_session_next_month'])),'validation_oos':metrics(window(f,*vo,x['entry_from_month_end'],x['exit_session_next_month']))};neighbors.append(q)
yearly={str(y):metrics([(d,r) for d,r in base if d.year==y]) for y in range(2017,2025)};boot=bootstrap(base,10000,168);g=s['robustness_gates'];pf=sum(x['full']['mean_return']>0 for x in neighbors);pv=sum(x['validation_oos']['mean_return']>0 for x in neighbors);py=sum(x['mean_return']>0 for x in yearly.values())
r={'schema_version':1,'preregistration_sha256':h,'holdout_2025_accessed':False,'candidate':metrics(base),'neighbors':neighbors,'yearly':yearly,'bootstrap':boot,'decision':{'pass':pf>=g['minimum_positive_neighbors_full_period'] and pv>=g['minimum_positive_neighbors_validation_oos'] and boot['probability_mean_positive']>=g['bootstrap_probability_mean_positive_gte'] and py>=g['minimum_positive_calendar_years'],'positive_neighbors_full':pf,'positive_neighbors_validation_oos':pv,'positive_years':py}}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
