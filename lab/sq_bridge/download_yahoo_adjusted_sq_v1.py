#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ticker',required=True);ap.add_argument('--start',required=True);ap.add_argument('--end',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);a=ap.parse_args()
    if dt.date.fromisoformat(a.end)>dt.date(2025,1,1):raise ValueError('sealed boundary exceeded')
    import yfinance as yf
    d=yf.download(a.ticker,start=a.start,end=a.end,auto_adjust=False,progress=False)
    if d.empty:raise RuntimeError('empty download')
    rows=[]
    for day,row in d.iterrows():
        date=day.date();
        if date.year>=2025:raise ValueError('sealed row')
        def val(name):return float(row[(name,a.ticker)] if (name,a.ticker) in row.index else row[name])
        close=val('Close');factor=val('Adj Close')/close
        rows.append((date.strftime('%Y.%m.%d'),'00:00',val('Open')*factor,val('High')*factor,val('Low')*factor,val('Adj Close'),val('Volume')))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w',newline='') as f:csv.writer(f,lineterminator='\n').writerows(rows)
    receipt={'schema_version':1,'ticker':a.ticker,'start':a.start,'end_exclusive':a.end,'rows':len(rows),'first':rows[0][0],'last':rows[-1][0],'adjusted_ohlc':True,'holdout_2025_accessed':False,'output_sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}
    a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
