#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=HERE/'overnight_premium_preregistration_v1.json'; LOCK=HERE/'overnight_premium_preregistration_v1.lock.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 if '2025' in p.name: raise ValueError('2025 sealed')
 out={}
 for line in p.read_text().splitlines():
  if not line.strip(): continue
  x=line.split(','); d=dt.datetime.strptime(x[0],'%Y.%m.%d').date()
  if d.year>=2025: raise ValueError('sealed row')
  out[d]=(float(x[2]),float(x[5]))
 return out
def returns(f,start,end,kind):
 ds=sorted(f); out=[]
 for i in range(1,len(ds)):
  if not start<=ds[i]<=end: continue
  r=f[ds[i]][0]/f[ds[i-1]][1]-1 if kind=='overnight' else f[ds[i]][1]/f[ds[i]][0]-1
  out.append((ds[i],r))
 return out
def basket(fs,start,end,kind):
 legs={a:dict(returns(f,start,end,kind)) for a,f in fs.items()}; common=sorted(set.intersection(*(set(v) for v in legs.values())))
 return [(d,sum(legs[a][d] for a in legs)/len(legs)) for d in common]
def metrics(rows):
 rs=[r for _,r in rows]; n=len(rs)
 if not n:return {'observations':0}
 mean=sum(rs)/n; sd=math.sqrt(sum((r-mean)**2 for r in rs)/(n-1)) if n>1 else 0
 gains=sum(r for r in rs if r>0); losses=-sum(r for r in rs if r<0)
 eq=peak=1.; dd=0.
 for r in rs:eq*=1+r;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'observations':n,'mean_return':mean,'total_return':eq-1,'profit_factor':gains/losses if losses else None,'t_stat':mean/(sd/math.sqrt(n)) if sd else None,'max_drawdown':dd}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--spx',type=Path,required=True);ap.add_argument('--stock',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 spec=json.loads(SPEC.read_text());lock=json.loads(LOCK.read_text())
 if sha(SPEC)!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
 paths=dict(x.split('=',1) for x in a.stock)
 if set(paths)!=set(spec['assets']['STOCKS']):raise ValueError('frozen universe required')
 spx=load(a.spx); stocks={k:load(Path(v)) for k,v in paths.items()}; raw={k:{} for k in ('SPX','STOCKS')}; report={'schema_version':1,'preregistration_sha256':sha(SPEC),'optimized':False,'holdout_2025_accessed':False,'periods':{}}
 for p,b in spec['periods'].items():
  if p=='holdout_2025':continue
  s,e=map(dt.date.fromisoformat,b); report['periods'][p]={}
  for label in raw:
   ov=returns(spx,s,e,'overnight') if label=='SPX' else basket(stocks,s,e,'overnight'); day=returns(spx,s,e,'intraday') if label=='SPX' else basket(stocks,s,e,'intraday')
   raw[label][p]=(ov,day);report['periods'][p][label]={'overnight':metrics(ov),'intraday':metrics(day)}
 g=spec['gates']; report['decisions']={}
 for label in raw:
  v,vd=raw[label]['validation'];o,od=raw[label]['oos_2024'];cm=metrics(v+o); cim=metrics(vd+od)
  passed=(len(v)>=g['validation_min_observations'] and len(o)>=g['oos_min_observations'] and metrics(v)['mean_return']>0 and metrics(o)['mean_return']>0 and (cm['t_stat'] or -999)>=g['combined_one_sided_t_stat_gte'] and (cm['profit_factor'] or 0)>=g['combined_profit_factor_gte'] and cm['mean_return']>cim['mean_return'])
  report['decisions'][label]={'pass':passed,'combined_validation_oos':{'overnight':cm,'intraday':cim}}
 report['transfer_gate_pass']=all(x['pass'] for x in report['decisions'].values());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
