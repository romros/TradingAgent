#!/usr/bin/env python3
"""Import the frozen KO D1 transfer resource through SQCLI."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lab.sq_bridge.sqcli_transport import docker_exec_http_call

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1/ko_resource/KOUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv"
INSIDE = "/home/squser/SQ/user/imports/alquimia_ko_pullback_v1/KO_D1.csv"
COMMANDS = [
    "-instrument action=add instrument=KO_IBKR_TREND_PULLBACK_V1 description=KO_D1_trend_pullback_transfer pointvalue=1 ticksize=0.001 tickstep=0.001 defaultspread=0 datatype=stock orderSizeMultiplier=1 orderSizeStep=1",
    "-symbol action=add symbols=KO_IBKR_TREND_PULLBACK_V1 instrument=KO_IBKR_TREND_PULLBACK_V1 datasource=file datatype=D1 postfix=_D1 exchange=NYSE",
    f"-data action=import symbol=KO_IBKR_TREND_PULLBACK_V1_D1 instrument=KO_IBKR_TREND_PULLBACK_V1 filepath={INSIDE} timezone=America/New_York timeframe=D1 bartype=startofbar errorhandling=stop format=MetaTrader4",
]


def main() -> None:
    subprocess.run(["docker", "exec", "sqcli-docker", "mkdir", "-p",
                    str(Path(INSIDE).parent)], check=True)
    subprocess.run(["docker", "cp", str(SOURCE), f"sqcli-docker:{INSIDE}"], check=True)
    print(json.dumps([{"command": command, "response": docker_exec_http_call(
        "sqcli-docker", command, timeout_seconds=120).strip()}
        for command in COMMANDS], indent=2))


if __name__ == "__main__":
    main()
