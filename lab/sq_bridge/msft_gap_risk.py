#!/usr/bin/env python3
"""Audita gaps de MSFT per al sizing preliminar del candidat mensual."""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import pandas as pd
from msft_python_validation import load_data


def percentile(values,q):
    values=sorted(values); return values[min(len(values)-1,math.ceil(len(values)*q)-1)] if values else None


def run(leverage=21, stop_pct=2.1):
    frame=load_data("1998-01-01","2026-08-02").copy(); prev=frame.close.shift(1)
    first=pd.Series(frame.index.to_period("M"),index=frame.index).ne(pd.Series(frame.index.to_period("M"),index=frame.index).shift(1)); first.iloc[0]=False
    frame=frame[first].copy(); frame["down_gap_pct"]=(1-frame.open/prev[first])*100; frame["intraday_adverse_pct"]=(1-frame.low/frame.open)*100
    threshold=100/leverage
    periods={"train":("1999-01-01","2012-10-16"),"validation":("2012-10-17","2018-04-23"),"oos":("2018-04-24","2023-10-29"),"holdout":("2023-10-30","2026-08-01")}
    rows={}
    for name,(start,end) in periods.items():
        sample=frame.loc[start:end]; gaps=[max(0,float(x)) for x in sample.down_gap_pct.dropna()]; adverse=[max(0,float(x)) for x in sample.intraday_adverse_pct.dropna()]
        rows[name]={"entries":len(sample),"max_down_gap_pct":max(gaps,default=None),"p99_down_gap_pct":percentile(gaps,.99),
          "gaps_beyond_stop":sum(x>=stop_pct for x in gaps),"gaps_beyond_liquidation_proxy":sum(x>=threshold for x in gaps),
          "intraday_moves_beyond_liquidation_if_stop_failed":sum(x>=threshold for x in adverse)}
    return {"schema_version":1,"data":"Yahoo MSFT unadjusted OHLC; execution parity with Ostium NOT certified","strategy":"first trading day monthly long",
      "stop_pct":stop_pct,"leverage":leverage,"liquidation_proxy_pct":threshold,"periods":rows,
      "verdict":"NOT_CERTIFIED_FOR_LIVE","reason":"Historical gap proxy is necessary but cannot establish Ostium oracle, stop fill, maintenance margin or liquidation behavior."}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,required=True); p.add_argument("--leverage",type=int,default=21); a=p.parse_args()
    result=run(a.leverage); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))
if __name__=="__main__": main()
