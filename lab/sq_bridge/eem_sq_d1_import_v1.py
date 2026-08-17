#!/usr/bin/env python3
"""Import the frozen EEM adjusted D1 source into the running SQ instance."""
import json
import subprocess
from pathlib import Path

from lab.sq_bridge.sqcli_transport import docker_exec_http_call

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/ibkr_sq_v2/eem_d1_simple_discovery_v1/EEM_ADJUSTED_D1_2017_2024_MT4.csv"
INSIDE = "/home/squser/SQ/user/imports/alquimia_eem_d1_v1/EEM_D1.csv"
COMMANDS = [
    "-instrument action=add instrument=EEM_IBKR_D1_V1 description=EEM_adjusted_D1 "
    "pointvalue=1 ticksize=0.000001 tickstep=0.000001 defaultspread=0 "
    "datatype=stock orderSizeMultiplier=1 orderSizeStep=1",
    "-symbol action=add symbols=EEM_IBKR_D1_V1 instrument=EEM_IBKR_D1_V1 "
    "datasource=file datatype=D1 postfix=_D1 exchange=NYSEARCA",
    f"-data action=import symbol=EEM_IBKR_D1_V1_D1 instrument=EEM_IBKR_D1_V1 "
    f"filepath={INSIDE} timezone=America/New_York timeframe=D1 bartype=startofbar "
    "errorhandling=stop format=MetaTrader4",
]


if __name__ == "__main__":
    subprocess.run(["docker", "exec", "sqcli-docker", "mkdir", "-p",
                    str(Path(INSIDE).parent)], check=True)
    subprocess.run(["docker", "cp", str(SOURCE), f"sqcli-docker:{INSIDE}"], check=True)
    print(json.dumps([
        {"command": command,
         "response": docker_exec_http_call("sqcli-docker", command, timeout_seconds=120).strip()}
        for command in COMMANDS
    ], indent=2))
