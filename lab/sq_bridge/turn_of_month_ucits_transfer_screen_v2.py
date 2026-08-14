#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load,trades,metrics
H=Path(__file__).resolve().parent;S=H/'turn_of_month_ucits_transfer_preregistration_v2.json';L=H/'turn_of_month_ucits_transfer_preregistration_v2.lock.json'
def corr(a,b):
 common=sorted(set(a)&set(b));x=[a[d] for d in common];y=[b[d] for d in common];mx=sum(x)/len(x);my=sum(y)/len(y);num=sum((u-mx)*(v-my) for u,v in zip(x,y));den=(sum((u-mx)**2 for u in x)*sum((v-my)**2 for v in y))**.5
 return {'observations':len(common),'correlation':num/den if den else None}
ap=argparse.ArgumentParser();ap.add_argument('--vuaa',type=Path,required=True);ap.add_argument('--spy',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
vuaa,spy=load(a.vuaa),load(a.spy);pt={};r={'schema_version':2,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'periods':{}}
for p,b in s['periods'].items():
 if p=='holdout_2025_plus':continue
 x=trades(vuaa,*map(dt.date.fromisoformat,b));pt[p]=x;r['periods'][p]=metrics(x)
v,o=metrics(pt['validation']),metrics(pt['oos_2024']);combined=pt['validation']+pt['oos_2024'];cm=metrics(combined);spyrows=trades(spy,dt.date(2022,1,1),dt.date(2024,12,31));co=corr(dict(combined),dict(spyrows));g=s['gates']
r['decision']={'pass':v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_profit_factor_gte'] and (cm['monthly_sharpe'] or -999)>=g['combined_monthly_sharpe_gte'] and cm['max_drawdown']<=g['combined_max_drawdown_lte'] and (co['correlation'] or -1)>=g['correlation_with_spy_monthly_returns_gte'],'combined_validation_oos':cm,'spy_correlation':co}
r['cost_diagnostics']={}
for cap in s['cost_diagnostics']['capital_eur']:
 commission=2*max(cap*s['cost_diagnostics']['ibkr_europe_tiered_rate'],s['cost_diagnostics']['minimum_per_order_eur'])
 for slip in s['cost_diagnostics']['roundtrip_slippage_bps']:
  cost=commission/cap+slip/10000;r['cost_diagnostics'][f'capital_{cap}_slippage_{slip}bps']={'roundtrip_cost_bps':cost*10000,'metrics':metrics([(d,x-cost) for d,x in combined])}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
