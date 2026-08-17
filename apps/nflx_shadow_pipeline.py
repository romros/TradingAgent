#!/usr/bin/env python3
"""Locked NFLX forward fetch -> receipt verification -> shadow state advance."""
from __future__ import annotations
import argparse,datetime as dt,fcntl,hashlib,json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,prefix='.'+path.name) as f:t=Path(f.name);json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 t.replace(path)
def run(cmd):
 x=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=180,check=False)
 if x.returncode:raise RuntimeError((x.stderr or x.stdout)[-1200:])
 return json.loads(x.stdout)
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',type=dt.date.fromisoformat,default=dt.date.today());p.add_argument('--capital',type=float,default=3000);p.add_argument('--skip-fetch',action='store_true');p.add_argument('--candles',type=Path,default=ROOT/'data/forward/NFLX_ADJUSTED_D1.csv');p.add_argument('--receipt',type=Path,default=ROOT/'data/forward/NFLX_ADJUSTED_D1.receipt.json');p.add_argument('--ledger',type=Path,default=ROOT/'data/shadow/nflx_04681.json');p.add_argument('--state',type=Path,default=ROOT/'data/shadow/nflx_04681_state.json');p.add_argument('--status',type=Path,default=ROOT/'data/shadow/nflx_04681_pipeline_status.json');p.add_argument('--lock',type=Path,default=ROOT/'data/shadow/nflx_04681_pipeline.lock');a=p.parse_args();a.lock.parent.mkdir(parents=True,exist_ok=True)
 with a.lock.open('a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise SystemExit('NFLX shadow pipeline already running')
  out={'schema_version':1,'pipeline':'nflx_04681_forward_shadow','as_of':a.as_of.isoformat(),'mode':'shadow','orders_sent':0,'paper_authorized':False,'live_authorized':False}
  try:
   if not a.skip_fetch:out['fetch']=run([sys.executable,str(ROOT/'apps/nflx_forward_fetch.py'),'--as-of',a.as_of.isoformat(),'--output',str(a.candles),'--receipt',str(a.receipt)])
   rec=json.loads(a.receipt.read_text())
   if rec.get('classification')!='FORWARD_ONLY_NOT_RESEARCH' or rec.get('split_adjusted') is not True or rec.get('performance_calculated') is not False:raise ValueError('unsafe NFLX forward receipt')
   if hashlib.sha256(a.candles.read_bytes()).hexdigest()!=rec.get('csv_sha256'):raise ValueError('NFLX forward hash mismatch')
   if (a.as_of-dt.date.fromisoformat(rec['last_session'])).days>5 or int(rec.get('sessions',0))<105:raise ValueError('stale or insufficient NFLX feed')
   out['receipt_verified']=True;out['scan']=run([sys.executable,str(ROOT/'apps/nflx_04681_shadow_daily.py'),'--candles',str(a.candles),'--ledger',str(a.ledger),'--state',str(a.state),'--capital',str(a.capital)]);out['status']='PASS'
  except Exception as e:out.update(status='FAIL_CLOSED',error=f'{type(e).__name__}: {e}')
  atomic(a.status,out);print(json.dumps(out,indent=2));raise SystemExit(0 if out['status']=='PASS' else 1)
if __name__=='__main__':main()
