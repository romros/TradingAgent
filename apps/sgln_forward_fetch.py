#!/usr/bin/env python3
"""Fetch completed SGLN.L adjusted D1 and GBPUSD for shadow economics."""
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.nflx_forward_fetch import atomic
def frame_lines(frame,ticker,as_of,completed,repair=False):
 lines=['date,open,high,low,close,volume'];repairs=0;maximum=0.
 for stamp,row in frame.iterrows():
  day=stamp.date()
  if day>as_of or (day==as_of and not completed):continue
  def v(k):return float(row[(k,ticker)] if (k,ticker) in row.index else row[k])
  o,h,l,c=(v(k) for k in ('Open','High','Low','Close'));fixed_h=max(h,o,c);fixed_l=min(l,o,c)
  if (fixed_h!=h or fixed_l!=l) and not repair:raise ValueError(f'invalid OHLC {ticker} {day}')
  if fixed_h!=h or fixed_l!=l:repairs+=1;maximum=max(maximum,abs(fixed_h-h),abs(fixed_l-l))
  lines.append(f'{day},{o:.8f},{fixed_h:.8f},{fixed_l:.8f},{c:.8f},{v("Volume"):.0f}')
 return lines,repairs,maximum
def main():
 p=argparse.ArgumentParser();p.add_argument('--as-of',type=dt.date.fromisoformat,default=dt.date.today());p.add_argument('--lookback-days',type=int,default=800);p.add_argument('--sgln-output',type=Path,required=True);p.add_argument('--fx-output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 import yfinance as yf
 start=a.as_of-dt.timedelta(days=a.lookback_days);end=(a.as_of+dt.timedelta(days=1)).isoformat();sg=yf.download('SGLN.L',start=start.isoformat(),end=end,auto_adjust=True,actions=False,progress=False);fx=yf.download('GBPUSD=X',start=start.isoformat(),end=end,auto_adjust=True,actions=False,progress=False)
 if sg.empty or fx.empty:raise RuntimeError('missing SGLN or GBPUSD forward data')
 now=dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo('Europe/London'));completed=now.date()>a.as_of or (now.date()==a.as_of and now.time()>=dt.time(16,45));sl,repairs,maximum=frame_lines(sg,'SGLN.L',a.as_of,completed,True);fl,_,_=frame_lines(fx,'GBPUSD=X',a.as_of,completed,True);sc='\n'.join(sl)+'\n';fc='\n'.join(fl)+'\n';atomic(a.sgln_output,sc);atomic(a.fx_output,fc);receipt={'schema_version':1,'classification':'FORWARD_ONLY_NOT_RESEARCH','ticker':'SGLN.L','fx_ticker':'GBPUSD=X','provider':'Yahoo Finance adjusted via yfinance','quote_units':'GBp; divide by 100 for GBP','current_incomplete_session_excluded':not completed,'first_session':sl[1].split(',')[0],'last_session':sl[-1].split(',')[0],'sessions':len(sl)-1,'sgln_csv_sha256':hashlib.sha256(sc.encode()).hexdigest(),'fx_csv_sha256':hashlib.sha256(fc.encode()).hexdigest(),'ohlc_envelope_repairs':repairs,'maximum_repair_gbp_pence':maximum,'performance_calculated':False,'orders_sent':0,'paper_authorized':False,'live_authorized':False};atomic(a.receipt,json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
