#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));from lab.sq_bridge.turn_of_month_screen_v1 import load
H=Path(__file__).resolve().parent;S=H/'bond_month_end_reversal_preregistration_v1.json';L=H/'bond_month_end_reversal_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def trades(frame):
 months={}
 for day in sorted(frame):months.setdefault((day.year,day.month),[]).append(day)
 out=[]
 for days in months.values():
  if len(days)<9:continue
  t8,t4,t3,t1=days[-9],days[-5],days[-4],days[-2]
  pressure=frame[t4][1]/frame[t8][1]-1
  if pressure<0:out.append((t3,t1,frame[t1][1]/frame[t3][0]-1,pressure))
 return out
def period(x,a,b):return [r for r in x if a<=r[0] and r[1]<=b]
def metrics(rows,cost):
 rs=[r[2]-cost/10000 for r in rows];n=len(rs)
 if not n:return {'trades':0}
 m=sum(rs)/n;sd=(sum((x-m)**2 for x in rs)/(n-1))**.5 if n>1 else 0;t=m/(sd/math.sqrt(n)) if sd else None;gp=sum(x for x in rs if x>0);gl=-sum(x for x in rs if x<0);eq=peak=1.;dd=0
 for x in rs:eq*=1+x;peak=max(peak,eq);dd=max(dd,1-eq/peak)
 return {'trades':n,'mean_return':m,'total_return':eq-1,'profit_factor':gp/gl if gl else None,'max_drawdown':dd,'t_stat':t,'one_sided_normal_p':.5*math.erfc((t or 0)/math.sqrt(2)) if t is not None else None}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--asset',action='append',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();s=json.loads(S.read_text());lock=json.loads(L.read_text());h=sha(S)
 if h!=lock['preregistration_sha256']:raise ValueError('lock mismatch')
 paths=dict(x.split('=',1) for x in a.asset)
 if set(paths)!=set(s['assets']):raise ValueError('exact assets required')
 report={'schema_version':1,'preregistration_sha256':h,'optimized':False,'holdout_2025_accessed':False,'assets':{}};passes={};g=s['gates']
 for asset,path in paths.items():
  raw=trades(load(Path(path)));block={'source_sha256':sha(path),'periods':{}}
  for p,bounds in s['periods'].items():
   if p=='holdout':continue
   sample=period(raw,*map(dt.date.fromisoformat,bounds));block['periods'][p]={k:metrics(sample,v) for k,v in s['costs_roundtrip_bps'].items()}
  sample=period(raw,dt.date.fromisoformat(s['periods']['validation'][0]),dt.date.fromisoformat(s['periods']['oos'][1]));block['combined_validation_oos']={k:metrics(sample,v) for k,v in s['costs_roundtrip_bps'].items()};passed=True
  for p in ('train','validation','oos'):
   m=block['periods'][p]['gross'];passed &= m['trades']>=g['minimum_trades'][p] and m['mean_return']>0 and (m['profit_factor'] or 0)>=g['each_period_gross_profit_factor_gte']
  passed &= (block['combined_validation_oos']['gross']['one_sided_normal_p'] or 1)<=g['combined_validation_oos_one_sided_normal_p_lte'];passes[asset]=bool(passed);block['pass']=bool(passed);report['assets'][asset]=block
 report['decision']={'status':'PASS_THIRD_EDGE_CANDIDATE' if all(passes.values()) else 'REJECT_BOND_MONTH_END_REVERSAL','asset_pass':passes,'paper_authorized':False,'live_authorized':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['decision'],indent=2))
if __name__=='__main__':main()
