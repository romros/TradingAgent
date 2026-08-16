#!/usr/bin/env python3
"""Import/export the frozen NFLX D1 resource through SQCLI."""
import argparse,json
from lab.sq_bridge.sqcli_transport import docker_exec_http_call
COMMANDS=[
 '-instrument action=add instrument=NFLX_IBKR_BREAKOUT_V1 description=NFLX_D1_breakout_research pointvalue=1 ticksize=0.001 tickstep=0.001 defaultspread=0 datatype=stock orderSizeMultiplier=1 orderSizeStep=1',
 '-symbol action=add symbols=NFLX_IBKR_BREAKOUT_V1 instrument=NFLX_IBKR_BREAKOUT_V1 datasource=file datatype=D1 postfix=_D1 exchange=NASDAQ',
 '-data action=import symbol=NFLX_IBKR_BREAKOUT_V1_D1 instrument=NFLX_IBKR_BREAKOUT_V1 filepath=/home/squser/SQ/user/imports/alquimia_nflx_breakout_v1/NFLXUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv timezone=America/New_York timeframe=D1 bartype=startofbar errorhandling=stop format=MetaTrader4',
 '-data action=export symbols=NFLX_IBKR_BREAKOUT_V1_D1 timeframe=D1 datefrom=2017.01.26 dateto=2024.12.31 outputdir=/home/squser/SQ/user/exports/alquimia_nflx_breakout_v1'
]
def main():
 p=argparse.ArgumentParser();p.add_argument('--export-only',action='store_true');a=p.parse_args();commands=COMMANDS[-1:] if a.export_only else COMMANDS;print(json.dumps([{'command':c,'response':docker_exec_http_call('sqcli-docker',c,timeout_seconds=120).strip()} for c in commands],indent=2))
if __name__=='__main__':main()
