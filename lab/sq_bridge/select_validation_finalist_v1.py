#!/usr/bin/env python3
"""Freeze one validation survivor before opening a sealed OOS period."""
from __future__ import annotations
import argparse,json,hashlib
from pathlib import Path
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();raw=a.gate.read_bytes();gate=json.loads(raw);rows=[r for r in gate['results'] if r['passed']]
 if not rows:raise ValueError('NO_VALIDATION_SURVIVOR')
 def key(r):
  m=r['audit']['results']['1000']['stress'];return (-m['profit_factor'],m['maximum_drawdown_pct_close_to_close'],-m['trades'],r['candidate_id'])
 winner=min(rows,key=key);result={'schema_version':1,'stage':'VALIDATION_FINALIST_FREEZE','selection_rule':'highest_stress_profit_factor_then_lowest_drawdown_then_most_trades','candidate_id':winner['candidate_id'],'validation_gate_sha256':hashlib.sha256(raw).hexdigest(),'oos_accessed_before_freeze':False,'paper_authorized':False,'live_authorized':False}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
