#!/usr/bin/env python3
"""Cross-provider adjusted-price confirmation after the gross OOS gate."""
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from lab.sq_bridge.etf_relative_momentum_screen_v1 import load, sha
from lab.sq_bridge.etf_twelve_one_momentum_screen_v1 import monthly_returns, one_sleeve_metrics

PERIODS={'train':(dt.date(2018,1,1),dt.date(2021,12,31)),'validation':(dt.date(2022,1,1),dt.date(2023,12,31)),'oos_2024':(dt.date(2024,1,1),dt.date(2024,12,31))}
def run(raw, adjusted, output):
    rf={k:load(v) for k,v in raw.items()}; af={k:load(v) for k,v in adjusted.items()}; results={}; agreements=[]
    for stage,bounds in PERIODS.items():
        rr=monthly_returns(rf,*bounds); ar=monthly_returns(af,*bounds)
        rm={r['entry'].isoformat():r for r in rr}; am={r['entry'].isoformat():r for r in ar}; common=sorted(set(rm)&set(am)); same=sum(rm[d]['selected']==am[d]['selected'] for d in common)
        results[stage]={'raw':one_sleeve_metrics(rr),'adjusted':one_sleeve_metrics(ar),'common_months':len(common),'same_selection_months':same,'selection_agreement':same/len(common)}; agreements.append(same/len(common))
    passed=min(agreements)>=.90 and results['validation']['adjusted']['total_return']>0 and results['oos_2024']['adjusted']['total_return']>0
    report={'schema_version':1,'decision':'PASS_ADJUSTED_CROSS_PROVIDER' if passed else 'REJECT_SOURCE_DEPENDENT','results':results,'raw_sha256':{k:sha(v) for k,v in raw.items()},'adjusted_sha256':{k:sha(v) for k,v in adjusted.items()},'holdout_2025_plus_accessed':False,'paper_authorized':False,'live_authorized':False}
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',action='append',required=True);p.add_argument('--adjusted',action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args(); parse=lambda xs:{k:Path(v) for k,v in (x.split('=',1) for x in xs)};print(json.dumps(run(parse(a.raw),parse(a.adjusted),a.output),indent=2))
if __name__=='__main__':main()
