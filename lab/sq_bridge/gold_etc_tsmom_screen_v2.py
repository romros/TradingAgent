#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.turn_of_month_screen_v1 import load
H=Path(__file__).resolve().parent;S=H/'gold_etc_tsmom_preregistration_v2.json';L=H/'gold_etc_tsmom_preregistration_v2.lock.json'
def monthly_rows(f,cost_change):
 months={}
 for d in sorted(f):months.setdefault((d.year,d.month),[]).append(d)
 keys=sorted(months);rows=[];old=0
 for i in range(12,len(keys)-1):
  signal_day=months[keys[i]][-1];next_days=months[keys[i+1]]
  if not next_days:continue
  following_key=keys[i+2] if i+2<len(keys) else None
  if following_key is None or following_key[0]*12+following_key[1]!=keys[i+1][0]*12+keys[i+1][1]+1:continue
  entry=next_days[0];exit_=months[following_key][0];position=int(f[signal_day][1]>f[months[keys[i-12]][-1]][1]);turn=abs(position-old);ret=position*(f[exit_][0]/f[entry][0]-1)-turn*cost_change;rows.append((entry,exit_,ret,position,turn));old=position
 return rows
def period(rows,start,end):return [x for x in rows if start<=x[0] and x[1]<=end]
def metrics(rows):
 rs=[x[2] for x in rows];n=len(rs)
 if not n:return {'months':0}
 m=sum(rs)/n;sd=math.sqrt(sum((x-m)**2 for x in rs)/(n-1)) if n>1 else 0;eq=peak=1.;dd=0.
 for x in rs:eq*=1+x;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'months':n,'invested_months':sum(x[3] for x in rows),'position_changes':sum(x[4] for x in rows),'total_return':eq-1,'annualized_return':eq**(12/n)-1,'annualized_sharpe':m/sd*math.sqrt(12) if sd else None,'max_drawdown':dd}
def corr(a,b):
 x={r[0]:r[2] for r in a};y={r[0]:r[2] for r in b};ks=sorted(set(x)&set(y));mx=sum(x[k] for k in ks)/len(ks);my=sum(y[k] for k in ks)/len(ks);den=(sum((x[k]-mx)**2 for k in ks)*sum((y[k]-my)**2 for k in ks))**.5
 return {'months':len(ks),'correlation':sum((x[k]-mx)*(y[k]-my) for k in ks)/den if den else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text());h=hashlib.sha256(S.read_bytes()).hexdigest()
 if h!=l['preregistration_sha256']:raise ValueError('lock mismatch')
 paths=dict(x.split('=',1) for x in a.asset);expected={x['id'] for x in s['instruments']}
 if set(paths)!=expected:raise ValueError('frozen instruments required')
 e=s['economics'];cost=e['commission_each_position_change_eur']/e['capital_eur_equivalent']+e['slippage_each_position_change_bps']/10000;raw={k:monthly_rows(load(Path(v)),cost) for k,v in paths.items()};report={'schema_version':2,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'assets':{},'decisions':{}}
 for asset,rows in raw.items():
  report['assets'][asset]={}
  for p,b in s['periods'].items():
   if p!='holdout_2025_plus':report['assets'][asset][p]=metrics(period(rows,*map(dt.date.fromisoformat,b)))
  v=report['assets'][asset]['validation'];o=report['assets'][asset]['oos'];combined=metrics(period(rows,dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1])));g=s['gates'];report['decisions'][asset]={'pass':v['months']>=g['validation_min_months'] and o['months']>=g['oos_min_months'] and v['total_return']>0 and o['total_return']>0 and (combined['annualized_sharpe'] or -999)>=g['combined_validation_oos_annualized_sharpe_gte'] and combined['max_drawdown']<=g['combined_validation_oos_max_drawdown_lte'],'combined_validation_oos':combined}
 lo,hi=dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1]);co=corr(period(raw['SGLN_L'],lo,hi),period(raw['PHAU_L'],lo,hi));report['transfer_correlation']=co;report['pass']=all(x['pass'] for x in report['decisions'].values()) and (co['correlation'] or -1)>=s['gates']['monthly_return_correlation_gte'];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
