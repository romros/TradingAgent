#!/usr/bin/env python3
"""Daily shadow-only scheduler; network is used only on scheduled action days."""
from __future__ import annotations
import argparse,datetime as dt,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def scheduled(calendar:Path,day:dt.date):
 value=json.loads(calendar.read_text());return any(x['date']==day.isoformat() for x in value['actions'])
def price(ticker:str,day:dt.date)->float:
 import yfinance as yf
 end=day+dt.timedelta(days=1);start=day-dt.timedelta(days=5);frame=yf.download(ticker,start=start.isoformat(),end=end.isoformat(),auto_adjust=False,progress=False)
 if frame.empty:raise RuntimeError('no executable reference price available')
 row=frame.iloc[-1]
 value=row[('Open',ticker)] if ('Open',ticker) in row.index else row['Open']
 return float(value)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--calendar',type=Path,default=ROOT/'data/ibkr_sq_v2/turn_of_month/sxr8_xetra_schedule_2026.json');ap.add_argument('--ledger',type=Path,default=ROOT/'data/shadow/sxr8_turn_of_month.json');ap.add_argument('--session',type=dt.date.fromisoformat,default=dt.date.today());ap.add_argument('--capital',type=float,default=1000);ap.add_argument('--ticker',default='SXR8.DE');a=ap.parse_args()
 if not scheduled(a.calendar,a.session):print(json.dumps({'session':a.session.isoformat(),'mode':'shadow','action':'NONE','network_accessed':False,'orders_sent':0}));return
 reference=price(a.ticker,a.session);cmd=[sys.executable,str(ROOT/'apps/sxr8_shadow_runner.py'),'--calendar',str(a.calendar),'--ledger',str(a.ledger),'--session',a.session.isoformat(),'--reference-price',str(reference),'--capital',str(a.capital)];result=subprocess.run(cmd,check=False,text=True,capture_output=True)
 if result.stdout:print(result.stdout,end='')
 if result.returncode:raise SystemExit(result.returncode)
if __name__=='__main__':main()
