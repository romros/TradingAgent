#!/usr/bin/env python3
"""Open the single locked 2024 GLD breakout OOS exactly once."""
from __future__ import annotations
import argparse,hashlib,json
from datetime import date
from pathlib import Path
from lab.sq_bridge.gld_d1_breakout_screen_v1 import load,trades,metrics
LOCK=Path('data/ibkr_sq_v2/gld_d1_breakout_v1/oos_selection_lock_v1.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();lock=json.loads(LOCK.read_text())
 if lock['oos_accessed'] is not False or lock['selected_candidate_id']!='GLD_BREAKOUT_E120_X60':raise ValueError('invalid locked selection')
 rows=load(a.source,allow_oos=True);values=trades(rows,lock['entry_lookback_sessions'],lock['exit_lookback_sessions']);window=(date(2024,1,1),date(2024,12,31));econ={str(cap):metrics(values,cap,*window) for cap in (500,1000)};m=econ['500'];passed=m['trades']>=1 and (m['profit_factor'] or 0)>=1.05 and m['return_pct']>0 and m['maximum_drawdown_pct']<=20
 out={'schema_version':1,'decision':'PASS_OOS_RESEARCH_EDGE' if passed else 'REJECT_OOS','candidate_id':lock['selected_candidate_id'],'lock_sha256':sha(LOCK),'source_sha256':sha(a.source),'period':['2024-01-01','2024-12-31'],'whole_share_ibkr_stress':econ,'completed_trade_details':[{'entry':x[0].isoformat(),'exit':x[1].isoformat(),'entry_price':x[2],'exit_price':x[3]} for x in values if window[0]<=x[0]<=window[1] and x[1]<=window[1]],'oos_accessed':True,'sqcli_authorized':passed,'paper_authorized':False,'live_authorized':False};a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
