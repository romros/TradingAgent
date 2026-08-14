#!/usr/bin/env python3
"""Frozen November-April equity seasonality transfer screen."""
import argparse,csv,hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;S=H/'halloween_equity_preregistration_v1.json';L=H/'halloween_equity_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load():
 s=json.loads(S.read_text());l=json.loads(L.read_text())
 if sha(S)!=l['preregistration_sha256'] or l['oos_2023_2024_accessed']:raise ValueError('lock mismatch')
 return s
def rows(p,allow):
 if '2025' in Path(p).name:raise ValueError('2025 refused')
 z=[]
 with Path(p).open(newline='') as f:
  for r in csv.reader(f):
   if not r or r[0].lower()=='date':continue
   d=r[0].replace('.','-')
   if d>('2024-12-31' if allow else '2022-12-31'):continue
   o=2 if len(r)>=7 and ':' in r[1] else 1;z.append((d,float(r[o])))
 return sorted(z)
def trades(z,b,cost):
 opens={}
 for d,o in z:opens.setdefault(d[:7],(d,o))
 out=[]
 for y in range(int(b[0][:4])-1,int(b[1][:4])+1):
  a=opens.get(f'{y}-11');x=opens.get(f'{y+1}-05')
  if a and x and b[0]<=x[0]<=b[1]:out.append({'entry':a[0],'exit':x[0],'return':x[1]/a[1]-1-cost/10000})
 return out
def met(t):
 eq=peak=1.;dd=w=l=0.
 for r in t:
  v=r['return'];eq*=1+v;peak=max(peak,eq);dd=max(dd,1-eq/peak);w+=max(v,0);l+=max(-v,0)
 return {'trades':len(t),'net_return':eq-1,'profit_factor':w/l if l else None,'maximum_drawdown':dd,'trades_detail':t}
def evaluate(data,s,b):return {a:met(trades(z,b,s['cost_bps'])) for a,z in data.items()}
def gate(v,g):
 flat=[r['return'] for a in v.values() for r in a['trades_detail']];w=sum(max(x,0) for x in flat);l=sum(max(-x,0) for x in flat)
 return all(a['trades']>=g['minimum_trades_per_asset_validation'] and a['maximum_drawdown']<=g['maximum_asset_drawdown'] for a in v.values()) and sum(a['net_return']>0 for a in v.values())>=g['minimum_positive_assets'] and l>0 and w/l>=g['minimum_pooled_profit_factor']
def screen(paths):
 s=load();pre={a:rows(p,False) for a,p in paths.items()};tr=evaluate(pre,s,s['periods']['train']);va=evaluate(pre,s,s['periods']['validation']);ok=gate(va,s['gate']);r={'schema_version':1,'preregistration_sha256':sha(S),'source_sha256':{a:sha(p) for a,p in paths.items()},'train':tr,'validation':va,'validation_gate_passed':ok,'decision':'PASS_VALIDATION_OPEN_OOS' if ok else 'REJECT_VALIDATION','oos_2023_2024_accessed':False,'holdout_2025_accessed':False,'optimized':False}
 if ok:r['oos']=evaluate({a:rows(p,True) for a,p in paths.items()},s,s['periods']['oos']);r['oos_2023_2024_accessed']=True
 return r
def main():
 p=argparse.ArgumentParser();p.add_argument('--asset',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=screen(dict(x.split('=',1) for x in a.asset));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
