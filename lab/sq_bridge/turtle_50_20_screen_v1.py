#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;SPEC=HERE/'turtle_50_20_preregistration_v1.json';LOCK=HERE/'turtle_50_20_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 if '2025' in p.name:raise ValueError('2025 sealed')
 z=[]
 for line in p.read_text().splitlines():
  if not line.strip():continue
  x=line.split(',');d=dt.datetime.strptime(x[0],'%Y.%m.%d').date()
  if d.year>=2025:raise ValueError('sealed row')
  z.append((d,float(x[2]),float(x[5])))
 return z
def trades(z):
 c=[x[2] for x in z];out=[];entry=None
 for i in range(50,len(z)-1):
  if entry is None and c[i]>max(c[i-50:i]):entry=(i+1,z[i+1][1])
  elif entry is not None and i>=entry[0] and c[i]<min(c[i-20:i]):out.append({'entry':z[entry[0]][0],'exit':z[i+1][0],'return':z[i+1][1]/entry[1]-1});entry=None
 return out
def period(ts,s,e):return [x for x in ts if s<=x['entry'] and x['exit']<=e]
def metrics(ts):
 r=[x['return'] for x in ts];n=len(r)
 if not n:return {'trades':0}
 m=sum(r)/n;sd=math.sqrt(sum((x-m)**2 for x in r)/(n-1)) if n>1 else 0;gp=sum(x for x in r if x>0);gl=-sum(x for x in r if x<0);eq=peak=1.;dd=0.
 for x in r:eq*=1+x;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'trades':n,'mean_return':m,'total_return':eq-1,'profit_factor':gp/gl if gl else None,'t_stat':m/(sd/math.sqrt(n)) if sd else None,'max_drawdown':dd}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(SPEC.read_text());l=json.loads(LOCK.read_text())
 if sha(SPEC)!=l['preregistration_sha256']:raise ValueError('lock mismatch')
 ps=dict(x.split('=',1) for x in a.asset)
 if set(ps)!=set(s['assets']):raise ValueError('frozen universe required')
 at={k:trades(load(Path(v))) for k,v in ps.items()};pt={};r={'schema_version':1,'preregistration_sha256':sha(SPEC),'optimized':False,'holdout_2025_accessed':False,'periods':{}}
 for p,b in s['periods'].items():
  if p=='holdout_2025':continue
  lo,hi=map(dt.date.fromisoformat,b);by={k:period(v,lo,hi) for k,v in at.items()};pool=sorted((x for v in by.values() for x in v),key=lambda x:x['exit']);pt[p]=pool;r['periods'][p]={'pooled':metrics(pool),'by_asset':{k:metrics(v) for k,v in by.items()}}
 g=s['gates'];v,o=metrics(pt['validation']),metrics(pt['oos_2024']);cm=metrics(sorted(pt['validation']+pt['oos_2024'],key=lambda x:x['exit']));positive=sum((r['periods']['validation']['by_asset'][k].get('total_return',0)+r['periods']['oos_2024']['by_asset'][k].get('total_return',0))>0 for k in ps)
 ok=(v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (cm['t_stat'] or -999)>=g['combined_one_sided_t_stat_gte'] and positive>=g['minimum_assets_positive_combined'] and cm['max_drawdown']<=g['combined_max_drawdown_lte'])
 r['decision']={'pass':ok,'combined_validation_oos':cm,'positive_assets':positive};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
