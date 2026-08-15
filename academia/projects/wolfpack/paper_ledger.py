#!/usr/bin/env python3
"""Finite unified paper ledger; merges sources without changing their evidence cohort."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def identity(source: str, trade: dict) -> str:
    natural = trade.get("position_sha256") or trade.get("experiment_id")
    return hashlib.sha256(f"{source}:{natural}".encode()).hexdigest()


def build(wolfpack: dict, standalone: list[dict]) -> dict:
    trades = []
    for status, key in (("OPEN", "open_positions"), ("CLOSED", "closed")):
        for row in wolfpack.get(key, []):
            trades.append({**row, "ledger_id": identity("wolfpack", row),
                           "source": "wolfpack", "status": status})
    seen = {row["ledger_id"] for row in trades}
    for row in standalone:
        if not row.get("status", "").startswith("CLOSED"):
            continue
        ledger_id = identity("standalone", row)
        if ledger_id in seen:
            continue
        seen.add(ledger_id)
        trades.append({**row, "ledger_id": ledger_id, "source": "standalone_setup",
                       "status": "CLOSED"})
    starting = float(wolfpack.get("starting_equity_usdc", 500))
    wolf_equity = float(wolfpack.get("ending_equity_usdc", starting))
    standalone_net = sum(float(row.get("copy_net_pnl_usdc") or 0)
                         for row in trades if row["source"] == "standalone_setup")
    incomplete = [row["ledger_id"] for row in trades
                  if row["status"] == "CLOSED" and not row.get("cost_complete", False)]
    return {"schema_version": 1, "mode": "UNIFIED_PAPER_NO_ORDERS",
            "starting_equity_usdc": starting,
            "ending_equity_usdc": wolf_equity + standalone_net,
            "wolfpack_ending_equity_usdc": wolf_equity,
            "standalone_net_pnl_usdc": standalone_net,
            "closed_count": sum(row["status"] == "CLOSED" for row in trades),
            "open_count": sum(row["status"] == "OPEN" for row in trades),
            "cost_complete": not incomplete, "incomplete_cost_ledger_ids": incomplete,
            "trades": trades, "live_trading_authorized": False}


def write_outputs(output: Path, csv_output: Path, ledger: dict) -> None:
    temporary = output.with_suffix(output.suffix + ".next")
    temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output)
    fields = ["ledger_id", "source", "status", "experiment_id", "position_sha256",
              "pair", "side", "entry_time", "exit_time", "entry_price", "exit_price",
              "copy_net_pnl_usdc", "cost_complete"]
    csv_temporary = csv_output.with_suffix(csv_output.suffix + ".next")
    with csv_temporary.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(ledger["trades"])
    csv_temporary.replace(csv_output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wolfpack", type=Path, required=True)
    parser.add_argument("--standalone-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv", dest="csv_output", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--duration-hours", type=float, default=720)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not 30 <= args.interval_seconds <= 3600 or not 0 < args.duration_hours <= 720:
        raise SystemExit("invalid finite cadence or duration")
    deadline = time.time() + args.duration_hours * 3600
    while time.time() < deadline:
        standalone = [read_json(path) for path in sorted(args.standalone_dir.glob("*-result.json"))]
        write_outputs(args.output, args.csv_output, build(read_json(args.wolfpack), standalone))
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
