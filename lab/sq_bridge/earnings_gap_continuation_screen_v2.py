#!/usr/bin/env python3
"""Run the frozen v1 gap rule on the preregistered expanded universe."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import earnings_gap_continuation_screen_v1 as engine

HERE=Path(__file__).resolve().parent
engine.SPEC=HERE/"earnings_gap_continuation_preregistration_v2.json"
engine.LOCK=HERE/"earnings_gap_continuation_preregistration_v2.lock.json"
engine.PREFLIGHT=engine.ROOT/"data/ibkr_sq_v2/earnings_gap_continuation_v1/sec_calendar_preflight_v2.json"

def main():
 p=argparse.ArgumentParser(); p.add_argument("--output",required=True,type=Path); a=p.parse_args()
 result=engine.screen(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,default=str)+"\n")
 print(json.dumps({k:result[k] for k in ("decision","periods","combined_validation_oos","positive_years","positive_assets","signals_executed")},indent=2))
if __name__=="__main__": main()
