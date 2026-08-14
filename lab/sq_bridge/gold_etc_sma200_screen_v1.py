#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load
from lab.sq_bridge.gold_etc_tsmom_screen_v2 import metrics,corr,period
H=Path(__file__).resolve().parent;S=H/'gold_etc_sma200_preregistration_v1.json';L=H/'gold_etc_sma200_preregistration_v1.lock.json'
def rows(f,cost):
 ds=sorted(f);months={}
 for i,d in enumerate(ds):months.setdefault((d.year,d.month),[]).append(i)
 keys=sorted(months);out=[];old=0
 for j in range(len(keys)-1):
  si=months[keys[j]][-1];ei=months[keys[j+1]][0]
  if si<199 or ei+1>=len(ds):continue
  next_key=keys[j+2] if j+2<len(keys) else None
  if next_key is None:continue
  xi=months[next_key][0];position=int(f[ds[si]][1]>sum(f[ds[k]][1] for k in range(si-199,si+1))/200);turn=abs(position-old);ret=position*(f[ds[xi]][0]/f[ds[ei]][0]-1)-turn*cost;out.append((ds[ei],ds[xi],ret,position,turn));old=position
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
 if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
 ps=dict(x.split('=',1) for x in a.asset);expected={x['id'] for x in s['instruments']}
 if set(ps)!=expected:raise ValueError('frozen instruments required')
 e=s['economics'];cost=e['commission_each_position_change_eur']/e['capital_eur_equivalent']+e['slippage_each_position_change_bps']/10000;raw={k:rows(load(Path(v)),cost) for k,v in ps.items()};r={'schema_version':1,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'assets':{},'decisions':{}}
 for asset,z in raw.items():
  r['assets'][asset]={p:metrics(period(z,*map(dt.date.fromisoformat,b))) for p,b in s['periods'].items() if p!='holdout_2025_plus'};combined=metrics(period(z,dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1])));m=r['assets'][asset];g=s['gates'];r['decisions'][asset]={'pass':m['train']['total_return']>g['train_return_gt'] and m['validation']['months']>=g['validation_min_months'] and m['oos']['months']>=g['oos_min_months'] and m['validation']['total_return']>0 and m['oos']['total_return']>0 and (combined['annualized_sharpe'] or -999)>=g['combined_annualized_sharpe_gte'] and combined['max_drawdown']<=g['combined_max_drawdown_lte'],'combined_validation_oos':combined}
 lo,hi=dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1]);co=corr(period(raw['SGLN_L'],lo,hi),period(raw['PHAU_L'],lo,hi));r['correlation']=co;r['pass']=all(x['pass'] for x in r['decisions'].values()) and (co['correlation'] or -1)>=s['gates']['monthly_return_correlation_gte'];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
