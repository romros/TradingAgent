#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load
H=Path(__file__).resolve().parent;S=H/'ucits_gap_fade_preregistration_v1.json';L=H/'ucits_gap_fade_preregistration_v1.lock.json'
def trades(f,start,end,cost):
 ds=sorted(f);out=[]
 for i in range(1,len(ds)):
  d=ds[i];open_,close=f[d];prior_close=f[ds[i-1]][1]
  if start<=d<=end and open_/prior_close-1<=-.01:out.append((d,close/open_-1-cost))
 return out
def metrics(rows):
 rs=[r for _,r in rows];n=len(rs)
 if not n:return {'trades':0}
 mean=sum(rs)/n;sd=math.sqrt(sum((x-mean)**2 for x in rs)/(n-1)) if n>1 else 0;gp=sum(x for x in rs if x>0);gl=-sum(x for x in rs if x<0);eq=1.
 for x in rs:eq*=1+x
 return {'trades':n,'wins':sum(x>0 for x in rs),'mean_return':mean,'total_return':eq-1,'profit_factor':gp/gl if gl else None,'t_stat':mean/(sd/math.sqrt(n)) if sd else None}
ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
ps=dict(x.split('=',1) for x in a.asset)
if set(ps)!=set(s['assets']):raise ValueError('frozen assets required')
cost=2*s['economics']['commission_each_order_eur']/s['economics']['capital_eur']+s['economics']['roundtrip_slippage_bps']/10000;r={'schema_version':1,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'assets':{},'decision':{}}
for asset,path in ps.items():
 f=load(Path(path));raw={};r['assets'][asset]={}
 for p,b in s['periods'].items():
  if p=='holdout_2025_plus':continue
  q=trades(f,*map(dt.date.fromisoformat,b),cost);raw[p]=q;r['assets'][asset][p]=metrics(q)
 v,o=metrics(raw['validation']),metrics(raw['oos']);c=metrics(raw['validation']+raw['oos']);g=s['gates'];r['decision'][asset]={'pass':v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_net_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_net_profit_factor_gte'] and (c['t_stat'] or -999)>=g['combined_net_t_stat_gte'],'combined':c}
r['transfer_pass']=all(x['pass'] for x in r['decision'].values());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
