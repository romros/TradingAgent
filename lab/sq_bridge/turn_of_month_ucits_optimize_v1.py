#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load,metrics
H=Path(__file__).resolve().parent;S=H/'turn_of_month_ucits_optimization_preregistration_v1.json';L=H/'turn_of_month_ucits_optimization_preregistration_v1.lock.json'
def window(f,start,end,eo,xd):
 ds=sorted(f);months={}
 for d in ds:months.setdefault((d.year,d.month),[]).append(d)
 keys=sorted(months);out=[]
 for i in range(len(keys)-1):
  current,following=keys[i],keys[i+1]
  if following[0]*12+following[1]!=current[0]*12+current[1]+1 or len(months[following])<xd:continue
  j=len(months[current])-1+eo
  if not 0<=j<len(months[current]):continue
  entry,exit_=months[current][j],months[following][xd-1]
  if entry<exit_ and start<=entry and exit_<=end:out.append((exit_,f[exit_][0]/f[entry][0]-1))
 return out
def net(rows,cost):return [(d,r-cost) for d,r in rows]
def neighbors(point,grid):
 e,x=point;allowed=set((a,b) for a in grid['entry_from_month_end'] for b in grid['exit_session_next_month'])
 return {(e-1,x),(e+1,x),(e,x-1),(e,x+1)}&allowed
ap=argparse.ArgumentParser();ap.add_argument('--vuaa',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
f=load(a.vuaa);sel=s['selection'];cost=(2*sel['commission_each_order_eur']/sel['capital_eur'])+sel['roundtrip_slippage_bps']/10000;dev=tuple(map(dt.date.fromisoformat,s['development']));rows=[]
for e in s['development_only_grid']['entry_from_month_end']:
 for x in s['development_only_grid']['exit_session_next_month']:
  m=metrics(net(window(f,*dev,e,x),cost));rows.append({'entry_from_month_end':e,'exit_session_next_month':x,'development_net':m})
index={(r['entry_from_month_end'],r['exit_session_next_month']):r for r in rows}
for r in rows:
 p=(r['entry_from_month_end'],r['exit_session_next_month']);r['positive_neighbors']=sum(index[n]['development_net'].get('mean_return',-1)>0 for n in neighbors(p,s['development_only_grid']))
eligible=[r for r in rows if r['development_net']['trades']>=sel['minimum_development_trades'] and r['positive_neighbors']>=sel['minimum_positive_orthogonal_neighbors'] and r['development_net'].get('mean_return',-1)>0]
eligible.sort(key=lambda r:(-(r['development_net'].get('monthly_sharpe') or -999),r['development_net']['max_drawdown'],r['exit_session_next_month']-r['entry_from_month_end'],r['entry_from_month_end'],r['exit_session_next_month']))
winner=eligible[0] if eligible else None;r={'schema_version':1,'preregistration_sha256':h,'optimized_on':'development_only','variants_tested':len(rows),'holdout_2025_accessed':False,'grid':rows,'winner':winner}
if winner:
 e,x=winner['entry_from_month_end'],winner['exit_session_next_month'];r['evaluation']={}
 for p in ('validation','oos_2024'):
  lo,hi=map(dt.date.fromisoformat,s[p]);r['evaluation'][p]=metrics(net(window(f,lo,hi,e,x),cost))
 lo=dt.date.fromisoformat(s['validation'][0]);hi=dt.date.fromisoformat(s['oos_2024'][1]);r['evaluation']['combined']=metrics(net(window(f,lo,hi,e,x),cost));v=r['evaluation']['validation'];o=r['evaluation']['oos_2024'];c=r['evaluation']['combined'];g=s['final_gates'];r['decision']={'pass':v['trades']>=g['validation_min_trades'] and o['trades']>=g['oos_min_trades'] and v['mean_return']>0 and o['mean_return']>0 and (v['profit_factor'] or 0)>=g['validation_and_oos_net_profit_factor_gte'] and (o['profit_factor'] or 0)>=g['validation_and_oos_net_profit_factor_gte'] and (c['monthly_sharpe'] or -999)>=g['combined_net_monthly_sharpe_gte'] and c['max_drawdown']<=g['combined_net_max_drawdown_lte'],'future_holdout_required':True}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'winner':winner,'evaluation':r.get('evaluation'),'decision':r.get('decision')},indent=2))
