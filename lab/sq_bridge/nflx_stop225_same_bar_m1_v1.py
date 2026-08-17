#!/usr/bin/env python3
"""Resolve the two same-session stop225 neighbor trades with canonical M1."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.nflx_04681_m1_execution_audit_v1 import first_touch, read_rth_minutes


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(m1_root: Path, orders_path: Path) -> dict:
    with orders_path.open(newline="", encoding="utf-8-sig") as handle:
        same = [row for row in csv.DictReader(handle, delimiter=";")
                if row["Open time"] == row["Close time"]]
    if len(same) != 2:
        raise ValueError("frozen stop225 same-bar count changed")
    dates = {row["Open time"][:10].replace(".", "-") for row in same}
    minutes = read_rth_minutes(m1_root, dates)
    rows = []
    for order in same:
        day = order["Open time"][:10].replace(".", "-")
        entry_price, target = float(order["Open price"]), float(order["Close price"])
        stop = entry_price - (target - entry_price) * 2.25 / 2.8
        entry = first_touch(minutes[day], entry_price, "up")
        target_touch = first_touch(minutes[day], target, "up", entry["ts"] if entry else None)
        stop_touch = first_touch(minutes[day], stop, "down", entry["ts"] if entry else None)
        feasible = bool(entry and target_touch and (not stop_touch or target_touch["ts"] < stop_touch["ts"]))
        rows.append({
            "ticket": order["Ticket"], "date": day, "rth_minutes": len(minutes[day]),
            "entry_price": entry_price, "target_price": target, "stop_price": stop,
            "entry_touch": entry["time"] if entry else None,
            "target_touch": target_touch["time"] if target_touch else None,
            "stop_touch": stop_touch["time"] if stop_touch else None,
            "chronologically_feasible": feasible,
        })
    checks = {"exactly_two_same_bar_trades": len(rows) == 2,
              "all_sessions_390_minutes": all(row["rth_minutes"] == 390 for row in rows),
              "both_targets_after_entry_before_stop": all(row["chronologically_feasible"] for row in rows)}
    return {
        "schema_version": 1,
        "decision": "PASS_STOP225_SAME_BAR_M1_FEASIBILITY" if all(checks.values())
                    else "REJECT_STOP225_SAME_BAR_M1_FEASIBILITY",
        "candidate_id": "NFLX04681_stop_225", "checks": checks,
        "orders_sha256": sha(orders_path), "trades": rows,
        "parameters_changed": False, "holdout_2025_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m1-root", type=Path, required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.m1_root, args.orders)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
