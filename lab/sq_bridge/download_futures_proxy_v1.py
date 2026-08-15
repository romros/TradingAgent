#!/usr/bin/env python3
"""Download frozen continuous-futures proxies; never certifies roll correctness."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
TICKERS={'ES':'ES=F','GC':'GC=F','CL':'CL=F','ZN':'ZN=F','EUR':'6E=F','JPY':'6J=F'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--instrument',choices=sorted(TICKERS),required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();ticker=TICKERS[a.instrument]
 import yfinance as yf
 data=yf.download(ticker,start='2008-01-01',end='2026-08-01',auto_adjust=False,progress=False)
 if data.empty:raise RuntimeError('empty download')
 rows=[]
 for stamp,row in data.iterrows():
  day=stamp.date()
  if day>__import__('datetime').date(2026,7,31):raise ValueError('future row')
  def value(name):return float(row[(name,ticker)] if (name,ticker) in row.index else row[name])
  close=value('Close');adjusted=value('Adj Close');factor=adjusted/close;rows.append((day.isoformat(),value('Open')*factor,value('High')*factor,value('Low')*factor,adjusted,value('Volume')))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as stream:
  writer=csv.writer(stream,lineterminator='\n');writer.writerow(('date','open','high','low','close','volume'));writer.writerows(rows)
 receipt={'schema_version':1,'instrument':a.instrument,'ticker':ticker,'continuous_proxy_only':True,'rows':len(rows),'first':rows[0][0],'last':rows[-1][0],'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()};a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
