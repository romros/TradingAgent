#!/usr/bin/env python3
"""Fetch a sealed adjusted-OHLC research window with an auditable receipt."""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from datetime import date
from pathlib import Path

SEAL=date(2025,1,1)

def atomic(path:Path,text:str):
 path.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,prefix='.'+path.name) as f:
  tmp=Path(f.name);f.write(text);f.flush();os.fsync(f.fileno())
 tmp.replace(path)

def main():
 p=argparse.ArgumentParser();p.add_argument('--ticker',required=True);p.add_argument('--start',type=date.fromisoformat,required=True);p.add_argument('--end-exclusive',type=date.fromisoformat,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 if not a.start<a.end_exclusive<=SEAL:raise ValueError('research window must end no later than 2025-01-01')
 import yfinance as yf
 frame=yf.download(a.ticker,start=a.start.isoformat(),end=a.end_exclusive.isoformat(),auto_adjust=True,actions=False,progress=False)
 if frame.empty:raise RuntimeError(f'no adjusted data for {a.ticker}')
 lines=['date,open,high,low,close,volume']
 for stamp,row in frame.iterrows():
  day=stamp.date()
  if not a.start<=day<a.end_exclusive:raise ValueError(f'row outside frozen window: {day}')
  def value(k):return float(row[(k,a.ticker)] if (k,a.ticker) in row.index else row[k])
  o,h,l,c=(value(k) for k in ('Open','High','Low','Close'))
  if l>min(o,c) or h<max(o,c) or l>h:raise ValueError(f'invalid OHLC: {day}')
  lines.append(f'{day},{o:.8f},{h:.8f},{l:.8f},{c:.8f},{value("Volume"):.0f}')
 content='\n'.join(lines)+'\n';atomic(a.output,content)
 receipt={'schema_version':1,'classification':'FROZEN_ADJUSTED_BENCHMARK_INPUT','ticker':a.ticker,'provider':'Yahoo Finance adjusted via yfinance','start':a.start.isoformat(),'end_exclusive':a.end_exclusive.isoformat(),'first_session':lines[1].split(',')[0],'last_session':lines[-1].split(',')[0],'sessions':len(lines)-1,'csv_sha256':hashlib.sha256(content.encode()).hexdigest(),'post_2024_accessed':False,'orders_sent':0}
 atomic(a.receipt,json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
