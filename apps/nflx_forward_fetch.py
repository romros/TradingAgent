#!/usr/bin/env python3
"""Fetch split-adjusted, completed NFLX D1 sessions for forward shadow only."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,os,tempfile
from pathlib import Path
from zoneinfo import ZoneInfo
def atomic(path,content):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,prefix='.'+path.name) as f:t=Path(f.name);f.write(content);f.flush();os.fsync(f.fileno())
 t.replace(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',type=dt.date.fromisoformat,default=dt.date.today());p.add_argument('--lookback-days',type=int,default=370);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if not 180<=a.lookback_days<=500:raise ValueError('lookback must be 180..500 days')
 import yfinance as yf
 start=a.as_of-dt.timedelta(days=a.lookback_days);frame=yf.download('NFLX',start=start.isoformat(),end=(a.as_of+dt.timedelta(days=1)).isoformat(),auto_adjust=True,actions=False,progress=False)
 if frame.empty:raise RuntimeError('no NFLX forward data')
 now=dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo('America/New_York'));completed_today=now.date()>a.as_of or (now.date()==a.as_of and now.time()>=dt.time(16,15))
 lines=['date,open,high,low,close,volume']
 for stamp,row in frame.iterrows():
  day=stamp.date()
  if day>a.as_of or (day==a.as_of and not completed_today):continue
  def v(k):return float(row[(k,'NFLX')] if (k,'NFLX') in row.index else row[k])
  o,h,l,c=(v(k) for k in ('Open','High','Low','Close'))
  if l>min(o,c) or h<max(o,c) or l>h:raise ValueError(f'invalid OHLC {day}')
  lines.append(f'{day},{o:.8f},{h:.8f},{l:.8f},{c:.8f},{v("Volume"):.0f}')
 content='\n'.join(lines)+'\n';atomic(a.output,content)
 receipt={'schema_version':1,'classification':'FORWARD_ONLY_NOT_RESEARCH','ticker':'NFLX','provider':'Yahoo Finance adjusted via yfinance','split_adjusted':True,'current_incomplete_session_excluded':not completed_today,'first_session':lines[1].split(',')[0],'last_session':lines[-1].split(',')[0],'sessions':len(lines)-1,'csv_sha256':hashlib.sha256(content.encode()).hexdigest(),'performance_calculated':False,'orders_sent':0,'paper_authorized':False,'live_authorized':False};atomic(a.receipt,json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
