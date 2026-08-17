#!/usr/bin/env python3
"""Frozen M1 execution adjudication for NFLX Strategy 0.4681."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
PREREG = HERE / "nflx_04681_m1_execution_preregistration_v1.json"
LOCK = HERE / "nflx_04681_m1_execution_preregistration_v1.lock.json"
NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_lock() -> dict:
    spec, lock = json.loads(PREREG.read_text()), json.loads(LOCK.read_text())
    if sha(PREREG) != lock["preregistration_sha256"]:
        raise ValueError("preregistration hash mismatch")
    if spec["selection_or_optimization_authorized"] is not False:
        raise ValueError("optimization must remain disabled")
    return spec


def norm_date(value: str) -> str:
    return value[:10].replace(".", "-")


def read_orders(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = [r for r in csv.DictReader(stream, delimiter=";") if r["Type"] == "Buy"]
    return [{
        "ticket": r["Ticket"], "open_date": norm_date(r["Open time"]),
        "open_price": float(r["Open price"]), "close_date": norm_date(r["Close time"]),
        "close_price": float(r["Close price"]), "close_type": r["Close type"],
    } for r in rows]


def read_rth_minutes(root: Path, wanted_dates: set[str]) -> dict[str, list[dict]]:
    result = {day: [] for day in wanted_dates}
    months = sorted({day[:7] for day in wanted_dates})
    for month in months:
        year, number = month.split("-")
        path = root / "tf=1m" / f"year={year}" / f"month={number}" / "data.csv.gz"
        if not path.is_file():
            raise FileNotFoundError(path)
        with gzip.open(path, "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                local = datetime.fromtimestamp(int(row["ts"]), UTC).astimezone(NY)
                day = local.date().isoformat()
                if day not in result or not (time(9, 30) <= local.time() < time(16, 0)):
                    continue
                result[day].append({
                    "ts": int(row["ts"]), "time": local.isoformat(),
                    "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]),
                })
    return result


def first_touch(bars: list[dict], price: float, side: str, start_ts: int | None = None) -> dict | None:
    for bar in bars:
        if start_ts is not None and bar["ts"] < start_ts:
            continue
        # A gap through a stop is executable at the observable open.  Including
        # open also makes the audit robust to documented raw-feed envelope
        # quirks such as high being one tick below open.
        if (side == "up" and (bar["open"] >= price or bar["high"] >= price)) or (
                side == "down" and (bar["open"] <= price or bar["low"] <= price)):
            return bar
    return None


def audit(m1_root: Path, orders_path: Path, parity_path: Path) -> dict:
    spec = verify_lock()
    orders = read_orders(orders_path)
    if len(orders) != 68:
        raise ValueError(f"frozen order count differs: {len(orders)}")
    wanted = set()
    for order in orders:
        start = datetime.fromisoformat(order["open_date"]).date()
        end = datetime.fromisoformat(order["close_date"]).date()
        # Only months containing actual trade dates are loaded below; all
        # intermediate sessions are added from the canonical calendar files.
        wanted.add(start.isoformat()); wanted.add(end.isoformat())
    # Include every canonical RTH session between the first entry and last exit.
    d1_path = Path(spec["frozen_history"].get(
        "canonical_d1", "data/ibkr_sq_v2/preflight/NFLXUSUSD_CANONICAL_D1_2017_2024.csv"))
    with d1_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.reader(stream):
            day = norm_date(row[0])
            if orders[0]["open_date"] <= day <= orders[-1]["close_date"]:
                wanted.add(day)
    minutes = read_rth_minutes(m1_root, wanted)
    session_counts = {day: len(bars) for day, bars in minutes.items()}
    bad_sessions = {day: count for day, count in session_counts.items() if count != 390}

    results, optimistic = [], []
    sorted_days = sorted(minutes)
    for order in orders:
        entry = first_touch(minutes[order["open_date"]], order["open_price"], "up")
        exit_side = "down" if order["close_type"] == "SL" else "up"
        exit_start = entry["ts"] if entry and order["open_date"] == order["close_date"] else None
        exit_bar = first_touch(minutes[order["close_date"]], order["close_price"], exit_side, exit_start)

        # Test whether the reported opposite bracket would have been crossed
        # earlier. The fixed 2.5:2.8 ratio lets one reported bracket infer the
        # other without refitting ATR.
        if order["close_type"] == "SL":
            risk = order["open_price"] - order["close_price"]
            opposite, opposite_side = order["open_price"] + risk * 2.8 / 2.5, "up"
        elif order["close_type"] == "PT":
            reward = order["close_price"] - order["open_price"]
            opposite, opposite_side = order["open_price"] - reward * 2.5 / 2.8, "down"
        else:
            opposite = None; opposite_side = None
        opposite_first = None
        if entry and opposite is not None:
            for day in sorted_days:
                if order["open_date"] <= day <= order["close_date"]:
                    hit = first_touch(minutes[day], opposite, opposite_side, entry["ts"] if day == order["open_date"] else None)
                    if hit:
                        opposite_first = hit; break
        feasible = entry is not None and exit_bar is not None
        contradicted = bool(opposite_first and exit_bar and opposite_first["ts"] < exit_bar["ts"])
        ambiguous = bool(opposite_first and exit_bar and opposite_first["ts"] == exit_bar["ts"])
        if not feasible or contradicted or ambiguous:
            optimistic.append(order["ticket"])
        results.append({
            **order,
            "entry_touch": entry["time"] if entry else None,
            "exit_touch": exit_bar["time"] if exit_bar else None,
            "opposite_bracket_price": round(opposite, 6) if opposite is not None else None,
            "opposite_touch": opposite_first["time"] if opposite_first else None,
            "feasible": feasible, "contradicted_by_earlier_opposite": contradicted,
            "same_minute_ambiguous": ambiguous,
        })
    parity = json.loads(parity_path.read_text())
    parity_ok = (parity.get("decision") == "PASS_INDEPENDENT_TRADE_PARITY"
                 and parity.get("mismatches") == []
                 and parity.get("sq_trades") == 68
                 and parity.get("simulated_trades") == 68)
    checks = {
        "all_sq_entries_m1_feasible": all(r["entry_touch"] for r in results),
        "all_sq_exits_m1_feasible": all(r["exit_touch"] for r in results),
        "zero_optimistic_ambiguous_trades": not optimistic,
        "all_rth_sessions_have_390_minutes": not bad_sessions,
        "independent_trade_sequence_explained": parity_ok,
    }
    return {
        "schema_version": 1,
        "decision": "PASS_M1_EXECUTION" if all(checks.values()) else "BLOCK_M1_EXECUTION",
        "candidate": spec["candidate"], "preregistration_sha256": sha(PREREG),
        "orders_path": str(orders_path), "orders_sha256": sha(orders_path),
        "parity_path": str(parity_path), "parity_sha256": sha(parity_path),
        "trades": len(results), "optimistic_or_infeasible_tickets": optimistic,
        "bad_rth_sessions": bad_sessions, "checks": checks, "trade_audit": results,
        "parameters_changed": False, "holdout_2025_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1-root", required=True, type=Path)
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--parity", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.m1_root, args.orders, args.parity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "decision", "trades", "optimistic_or_infeasible_tickets", "checks")}, indent=2))


if __name__ == "__main__":
    main()
