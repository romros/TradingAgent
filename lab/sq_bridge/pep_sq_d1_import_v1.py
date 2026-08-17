#!/usr/bin/env python3
"""Import and export the frozen PEP D1 resource through SQCLI."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from lab.sq_bridge.sqcli_transport import docker_exec_http_call

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/PEPUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv"
IMPORT = "/home/squser/SQ/user/imports/alquimia_pep_pullback_v1/PEP_D1.csv"
EXPORT_DIR = "/home/squser/SQ/user/exports/alquimia_pep_pullback_v1"
COMMANDS = [
    "-instrument action=add instrument=PEP_IBKR_TREND_PULLBACK_V1 description=PEP_D1_trend_pullback_research pointvalue=1 ticksize=0.001 tickstep=0.001 defaultspread=0 datatype=stock orderSizeMultiplier=1 orderSizeStep=1",
    "-symbol action=add symbols=PEP_IBKR_TREND_PULLBACK_V1 instrument=PEP_IBKR_TREND_PULLBACK_V1 datasource=file datatype=D1 postfix=_D1 exchange=NASDAQ",
    f"-data action=import symbol=PEP_IBKR_TREND_PULLBACK_V1_D1 instrument=PEP_IBKR_TREND_PULLBACK_V1 filepath={IMPORT} timezone=America/New_York timeframe=D1 bartype=startofbar errorhandling=stop format=MetaTrader4",
    f"-data action=export symbols=PEP_IBKR_TREND_PULLBACK_V1_D1 timeframe=D1 datefrom=2017.11.02 dateto=2024.12.31 outputdir={EXPORT_DIR}",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    subprocess.run(["docker", "exec", "sqcli-docker", "mkdir", "-p",
                    str(Path(IMPORT).parent), EXPORT_DIR], check=True)
    if not args.export_only:
        subprocess.run(["docker", "cp", str(SOURCE), f"sqcli-docker:{IMPORT}"], check=True)
    commands = COMMANDS[-1:] if args.export_only else COMMANDS
    results = [{"command": command, "response": docker_exec_http_call(
        "sqcli-docker", command, timeout_seconds=120).strip()} for command in commands]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
