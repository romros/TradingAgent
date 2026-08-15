#!/usr/bin/env python3
import argparse,csv,hashlib,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--ticker',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();import yfinance as yf
 d=yf.download(a.ticker,start='2024-09-01',end='2026-08-15',auto_adjust=False,progress=False);rows=[]
 for stamp,row in d.iterrows():
  day=stamp.date()
  if day.isoformat()>'2026-08-14':raise ValueError('FUTURE_ROW')
  def v(n):return float(row[(n,a.ticker)] if (n,a.ticker) in row.index else row[n])
  f=v('Adj Close')/v('Close');rows.append((day.isoformat(),v('Open')*f,v('High')*f,v('Low')*f,v('Adj Close')))
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('w',newline='') as h:w=csv.writer(h,lineterminator='\n');w.writerow(('date','open','high','low','close'));w.writerows(rows)
 receipt={'ticker':a.ticker,'rows':len(rows),'first':rows[0][0],'last':rows[-1][0],'adjusted':True,'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()};a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
