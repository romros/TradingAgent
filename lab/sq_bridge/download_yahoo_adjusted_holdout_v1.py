#!/usr/bin/env python3
"""Download the frozen AAPL confirmation interval as adjusted OHLC."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 import yfinance as yf
 data=yf.download('AAPL',start='2025-01-02',end='2026-08-01',auto_adjust=False,progress=False)
 if data.empty: raise RuntimeError('empty download')
 rows=[]
 for stamp,row in data.iterrows():
  day=stamp.date()
  if not __import__('datetime').date(2025,1,2)<=day<=__import__('datetime').date(2026,7,31): raise ValueError('row outside frozen interval')
  def value(name): return float(row[(name,'AAPL')] if (name,'AAPL') in row.index else row[name])
  close=value('Close');factor=value('Adj Close')/close;rows.append((day.isoformat(),value('Open')*factor,value('High')*factor,value('Low')*factor,value('Adj Close'),value('Volume')))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as stream:
  writer=csv.writer(stream,lineterminator='\n');writer.writerow(('date','open','high','low','close','volume'));writer.writerows(rows)
 receipt={'schema_version':1,'ticker':'AAPL','interval':['2025-01-02','2026-07-31'],'rows':len(rows),'first':rows[0][0],'last':rows[-1][0],'adjusted_ohlc':True,'output_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()};a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
