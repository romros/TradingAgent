#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from lab.sq_bridge.nflx_04681_risk_overlay_v1 import load,commission
H=Path(__file__).resolve().parent;S=H/'nflx_04681_daily_mtm_preregistration_v1.json';L=H/'nflx_04681_daily_mtm_preregistration_v1.lock.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dd(curve):
 peak=curve[0]['equity'];worst=0;peak_day=curve[0]['date'];out={}
 for x in curve:
  if x['equity']>peak:peak=x['equity'];peak_day=x['date']
  now=(peak-x['equity'])/peak
  if now>worst:worst=now;out={'peak_date':peak_day,'trough_date':x['date'],'peak_equity':peak,'trough_equity':x['equity']}
 return worst*100,out
def main():
 p=argparse.ArgumentParser();p.add_argument('--orders',type=Path,required=True);p.add_argument('--d1',type=Path,required=True);p.add_argument('--risk',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=json.loads(S.read_text());l=json.loads(L.read_text())
 if sha(S)!=l['preregistration_sha256'] or sha(a.d1)!=s['canonical_d1_sha256'] or sha(a.risk)!=s['risk_overlay_sha256']:raise ValueError('frozen input mismatch')
 rows=load(a.orders);prices={};
 with a.d1.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.reader(f):prices[r[0].replace('.','-')]=float(r[5])
 equity=3000.;curve=[]
 for t in rows:
  shares=math.floor(equity*.75/(t['open']*1.001+commission(1)));cash=equity-shares*t['open']*1.001-commission(shares)
  for day,close in prices.items():
   if t['open_date']<=day<=t['close_date']:curve.append({'date':day,'equity':cash+shares*close*(1-.001)-commission(shares)})
  equity=cash+shares*t['close']*(1-.001)-commission(shares);curve.append({'date':t['close_date'],'equity':equity})
 strategy_dd,episode=dd(sorted(curve,key=lambda x:x['date']))
 first,last=rows[0],rows[-1];shares=math.floor((3000-commission(1))/(first['open']*1.001));cash=3000-shares*first['open']*1.001-commission(shares);bc=[{'date':d,'equity':cash+shares*c*(1-.001)-commission(shares)} for d,c in prices.items() if first['open_date']<=d<=last['close_date']];bench_dd,bench_episode=dd(sorted(bc,key=lambda x:x['date']))
 out={'schema_version':1,'decision':'PASS_DAILY_MTM_VETO' if strategy_dd<=20 else 'FAIL_DAILY_MTM_VETO','exposure_fraction':.75,'strategy_daily_mtm_drawdown_pct':strategy_dd,'strategy_worst_episode':episode,'buy_hold_daily_mtm_drawdown_pct':bench_dd,'buy_hold_worst_episode':bench_episode,'daily_points':len(curve),'holdout_2025_accessed':False,'paper_authorized':False,'live_authorized':False};a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
