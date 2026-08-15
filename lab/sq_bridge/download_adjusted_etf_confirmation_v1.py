#!/usr/bin/env python3
"""Download split/dividend-adjusted ETF D1 confirmation data through 2024."""
from __future__ import annotations
import argparse, csv, hashlib, json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--ticker',required=True); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--receipt',type=Path,required=True); args=parser.parse_args()
    import yfinance as yf
    data=yf.download(args.ticker,start='2017-01-01',end='2025-01-01',auto_adjust=False,progress=False)
    if data.empty: raise RuntimeError('empty confirmation source')
    rows=[]
    for stamp,row in data.iterrows():
        day=stamp.date()
        if day.year>=2025: raise ValueError('HOLDOUT_ROW_SEALED')
        def value(name): return float(row[(name,args.ticker)] if (name,args.ticker) in row.index else row[name])
        factor=value('Adj Close')/value('Close')
        rows.append((day.isoformat(),value('Open')*factor,value('High')*factor,value('Low')*factor,value('Adj Close')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',newline='') as handle:
        writer=csv.writer(handle,lineterminator='\n'); writer.writerow(('date','open','high','low','close')); writer.writerows(rows)
    receipt={'schema_version':1,'ticker':args.ticker,'provider':'Yahoo via yfinance','adjusted_ohlc':True,'end_exclusive':'2025-01-01','rows':len(rows),'first':rows[0][0],'last':rows[-1][0],'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'holdout_2025_plus_accessed':False}
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt))
if __name__=='__main__': main()
