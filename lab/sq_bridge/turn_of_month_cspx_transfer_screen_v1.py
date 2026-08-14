#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load,trades,metrics
H=Path(__file__).resolve().parent;S=H/'turn_of_month_cspx_transfer_preregistration_v1.json';L=H/'turn_of_month_cspx_transfer_preregistration_v1.lock.json'
def correlation(a,b):
 keys=sorted(set(a)&set(b));x=[a[k] for k in keys];y=[b[k] for k in keys];mx=sum(x)/len(x);my=sum(y)/len(y);den=(sum((v-mx)**2 for v in x)*sum((v-my)**2 for v in y))**.5
 return {'observations':len(keys),'correlation':sum((u-mx)*(v-my) for u,v in zip(x,y))/den if den else None}
ap=argparse.ArgumentParser();ap.add_argument('--listing',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
paths=dict(x.split('=',1) for x in a.listing);expected={x['id'] for x in s['fund']['listings']}
if set(paths)!=expected:raise ValueError('frozen listings required')
frames={k:load(Path(v)) for k,v in paths.items()};raw={};r={'schema_version':1,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'listings':{}}
for asset,f in frames.items():
 raw[asset]={};r['listings'][asset]={}
 for p,b in s['periods'].items():
  if p=='holdout_2025_plus':continue
  q=trades(f,*map(dt.date.fromisoformat,b));raw[asset][p]=q;r['listings'][asset][p]=metrics(q)
g=s['gates'];dec={}
for asset in frames:
 v,o=metrics(raw[asset]['validation']),metrics(raw[asset]['oos']);c=metrics(raw[asset]['validation']+raw[asset]['oos']);dec[asset]={'pass':v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['each_period_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['each_period_profit_factor_gte'] and (c['monthly_sharpe'] or -999)>=g['combined_monthly_sharpe_gte'] and c['max_drawdown']<=g['combined_max_drawdown_lte'],'combined':c}
co=correlation(dict(raw['SXR8_DE']['validation']+raw['SXR8_DE']['oos']),dict(raw['CSPX_L']['validation']+raw['CSPX_L']['oos']));r['decision']={'pass':all(x['pass'] for x in dec.values()) and (co['correlation'] or -1)>=g['listing_return_correlation_gte'],'by_listing':dec,'correlation':co}
for asset in frames:
 r['listings'][asset]['cost_1000_eur']={}
 rows=raw[asset]['validation']+raw[asset]['oos']
 for slip in s['cost_diagnostic']['roundtrip_slippage_bps']:
  cost=2*s['cost_diagnostic']['commission_each_order_eur']/1000+slip/10000;r['listings'][asset]['cost_1000_eur'][f'slippage_{slip}bps']=metrics([(d,x-cost) for d,x in rows])
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
