#!/usr/bin/env python3
"""Unchanged TSMOM12 transfer from IDTL to shorter-duration IBTM."""
from __future__ import annotations
import argparse,json
from datetime import date
from pathlib import Path
from lab.sq_bridge.idtl_tsmom12_screen_v1 import sha,load,rows,metrics

EXPECTED='f6035f4f3d8ca02f0f8fabacd7e211ccc010320972c78ffd9e479b9ab0a0537a'
PERIODS={'train':(date(2010,1,1),date(2021,12,31)),'validation':(date(2022,1,1),date(2023,12,31)),'oos':(date(2024,1,1),date(2024,12,31)),'combined':(date(2022,1,1),date(2024,12,31))}
def run(path):
 if sha(path)!=EXPECTED:raise ValueError('frozen IBTM hash mismatch')
 xs=rows(load(path));result={k:metrics([x for x in xs if a<=x[0]<=b]) for k,(a,b) in PERIODS.items()};c=result['combined']
 passed=all(result[k]['total_return']>0 for k in ('train','validation','oos')) and c['annualized_sharpe']>=.4 and c['maximum_drawdown']<=.2 and c['invested_months']>=12
 return {'schema_version':1,'decision':'PASS_IBTM_TSMOM12_EDGE' if passed else 'REJECT_IBTM_TSMOM12','source_sha256':sha(path),'rule_transfer_changed':False,'periods':result,'optimized':False,'post_2024_accessed':False,'paper_authorized':False,'live_authorized':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('data',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.data);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if __name__=='__main__':main()
