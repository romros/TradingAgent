#!/usr/bin/env python3
"""Locked JPM fetch, receipt verification and forward-only shadow advance."""
from __future__ import annotations
import argparse,datetime as dt,fcntl,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.nflx_shadow_pipeline import ROOT,atomic,run
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',type=dt.date.fromisoformat,default=dt.date.today());p.add_argument('--capital',type=float,default=500);p.add_argument('--skip-fetch',action='store_true');p.add_argument('--candles',type=Path,default=ROOT/'data/forward/JPM_ADJUSTED_D1.csv');p.add_argument('--receipt',type=Path,default=ROOT/'data/forward/JPM_ADJUSTED_D1.receipt.json');p.add_argument('--ledger',type=Path,default=ROOT/'data/shadow/jpm_momentum60.json');p.add_argument('--state',type=Path,default=ROOT/'data/shadow/jpm_momentum60_state.json');p.add_argument('--status',type=Path,default=ROOT/'data/shadow/jpm_momentum60_pipeline_status.json');p.add_argument('--lock',type=Path,default=ROOT/'data/shadow/jpm_momentum60_pipeline.lock');a=p.parse_args();a.lock.parent.mkdir(parents=True,exist_ok=True)
 with a.lock.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('JPM shadow pipeline already running')
  out={'schema_version':1,'pipeline':'jpm_momentum60_forward_shadow','as_of':a.as_of.isoformat(),'mode':'shadow','orders_sent':0,'paper_authorized':False,'live_authorized':False}
  try:
   if not a.skip_fetch:out['fetch']=run([sys.executable,str(ROOT/'apps/jpm_forward_fetch.py'),'--as-of',a.as_of.isoformat(),'--output',str(a.candles),'--receipt',str(a.receipt)])
   rec=json.loads(a.receipt.read_text())
   if rec.get('classification')!='FORWARD_ONLY_NOT_RESEARCH' or rec.get('performance_calculated') is not False:raise ValueError('unsafe JPM receipt')
   if hashlib.sha256(a.candles.read_bytes()).hexdigest()!=rec.get('csv_sha256'):raise ValueError('JPM hash mismatch')
   if (a.as_of-dt.date.fromisoformat(rec['last_session'])).days>5 or int(rec.get('sessions',0))<100:raise ValueError('stale or insufficient JPM feed')
   out['receipt_verified']=True;out['scan']=run([sys.executable,str(ROOT/'apps/jpm_momentum60_shadow_daily.py'),'--candles',str(a.candles),'--ledger',str(a.ledger),'--state',str(a.state),'--capital',str(a.capital)]);out['status']='PASS'
  except Exception as e:out.update(status='FAIL_CLOSED',error=f'{type(e).__name__}: {e}')
  atomic(a.status,out);print(json.dumps(out,indent=2));raise SystemExit(0 if out['status']=='PASS' else 1)
if __name__=='__main__':main()
