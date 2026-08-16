#!/usr/bin/env python3
"""Import and export the frozen XLF D1 research resource through SQCLI."""
from __future__ import annotations

import argparse
import json

from lab.sq_bridge.sqcli_transport import docker_exec_http_call


COMMANDS = [
    "-instrument action=add instrument=XLF_IBKR_V1 description=XLF_adjusted_D1_gross_research pointvalue=1 ticksize=0.000001 tickstep=0.000001 defaultspread=0 datatype=stock orderSizeMultiplier=1 orderSizeStep=1",
    "-symbol action=add symbols=XLF_IBKR_V1 instrument=XLF_IBKR_V1 datasource=file datatype=D1 postfix=_D1 exchange=NYSEARCA",
    "-data action=import symbol=XLF_IBKR_V1_D1 instrument=XLF_IBKR_V1 filepath=/home/squser/SQ/user/imports/alquimia_xlf_v1/XLF_ADJUSTED_D1_2017_2024_MT4.csv timezone=America/New_York timeframe=D1 bartype=startofbar errorhandling=stop format=MetaTrader4",
    "-data action=export symbols=XLF_IBKR_V1_D1 timeframe=D1 datefrom=2017.01.26 dateto=2024.12.31 outputdir=/home/squser/SQ/user/exports/alquimia_xlf_d1_roundtrip_v1",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    responses = []
    commands = COMMANDS[-1:] if args.export_only else COMMANDS
    for command in commands:
        body = docker_exec_http_call("sqcli-docker", command, timeout_seconds=120)
        responses.append({"command": command, "response": body.strip()})
    print(json.dumps(responses, indent=2))


if __name__ == "__main__":
    main()
