#!/usr/bin/env python3
"""Locked SGLN/GBPUSD fetch and TSMOM12 shadow advance."""
from __future__ import annotations
import argparse,datetime as dt,fcntl,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.nflx_shadow_pipeline import ROOT,atomic,run
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',type=dt.date.fromisoformat,default=dt.date.today());p.add_argument('--capital',type=float,default=500);p.add_argument('--skip-fetch',action='store_true');p.add_argument('--candles',type=Path,default=ROOT/'data/forward/SGLN_ADJUSTED_D1.csv');p.add_argument('--fx',type=Path,default=ROOT/'data/forward/GBPUSD_D1.csv');p.add_argument('--receipt',type=Path,default=ROOT/'data/forward/SGLN_ADJUSTED_D1.receipt.json');p.add_argument('--ledger',type=Path,default=ROOT/'data/shadow/sgln_tsmom12.json');p.add_argument('--state',type=Path,default=ROOT/'data/shadow/sgln_tsmom12_state.json');p.add_argument('--status',type=Path,default=ROOT/'data/shadow/sgln_tsmom12_pipeline_status.json');p.add_argument('--lock',type=Path,default=ROOT/'data/shadow/sgln_tsmom12_pipeline.lock');a=p.parse_args();a.lock.parent.mkdir(parents=True,exist_ok=True)
 with a.lock.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('SGLN shadow pipeline already running')
  out={'schema_version':1,'pipeline':'sgln_tsmom12_forward_shadow','as_of':a.as_of.isoformat(),'mode':'shadow','orders_sent':0,'paper_authorized':False,'live_authorized':False}
  try:
   if not a.skip_fetch:out['fetch']=run([sys.executable,str(ROOT/'apps/sgln_forward_fetch.py'),'--as-of',a.as_of.isoformat(),'--sgln-output',str(a.candles),'--fx-output',str(a.fx),'--receipt',str(a.receipt)])
   rec=json.loads(a.receipt.read_text())
   if rec.get('classification')!='FORWARD_ONLY_NOT_RESEARCH' or rec.get('performance_calculated') is not False or rec.get('quote_units')!='GBp; divide by 100 for GBP':raise ValueError('unsafe SGLN receipt')
   if hashlib.sha256(a.candles.read_bytes()).hexdigest()!=rec.get('sgln_csv_sha256') or hashlib.sha256(a.fx.read_bytes()).hexdigest()!=rec.get('fx_csv_sha256'):raise ValueError('SGLN/FX hash mismatch')
   if (a.as_of-dt.date.fromisoformat(rec['last_session'])).days>7 or int(rec.get('sessions',0))<260:raise ValueError('stale or insufficient SGLN feed')
   out['receipt_verified']=True;out['scan']=run([sys.executable,str(ROOT/'apps/sgln_tsmom12_shadow_daily.py'),'--candles',str(a.candles),'--fx',str(a.fx),'--ledger',str(a.ledger),'--state',str(a.state),'--capital',str(a.capital)]);out['status']='PASS'
  except Exception as e:out.update(status='FAIL_CLOSED',error=f'{type(e).__name__}: {e}')
  atomic(a.status,out);print(json.dumps(out,indent=2));raise SystemExit(0 if out['status']=='PASS' else 1)
if __name__=='__main__':main()
