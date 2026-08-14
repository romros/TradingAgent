#!/usr/bin/env python3
"""Replay one completed CAT session into a broker-neutral shadow ledger."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.execution.shadow import (ShadowIntent, append_once,
    hypothetical_open_intent, hypothetical_position, load_ledger, sync_csv, whole_share_size)
from packages.strategy.cat_adx_d1 import bracket_exit, entry_for_index


def load_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {"date", "open", "high", "low", "close"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("canonical date/open/high/low/close CSV required")
    rows.sort(key=lambda row: row["date"])
    if len({row["date"] for row in rows}) != len(rows):
        raise ValueError("duplicate sessions")
    for row in rows:
        opening, high, low, close = (float(row[key]) for key in ("open", "high", "low", "close"))
        if low > min(opening, close) or high < max(opening, close) or low > high:
            raise ValueError(f"invalid OHLC envelope on {row['date']}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candles", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, default=ROOT / "data/shadow/cat_0168.json")
    ap.add_argument("--session", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--commission", type=float, default=1.0)
    args = ap.parse_args()
    rows = load_rows(args.candles)
    matches = [i for i, row in enumerate(rows) if row["date"] == args.session.isoformat()]
    report = {"schema_version": 1, "mode": "shadow", "strategy": "cat_0168",
              "session": args.session.isoformat(), "orders_sent": 0,
              "created": [], "action": "NONE"}
    if not matches:
        report.update(action="BLOCKED_MISSING_COMPLETED_SESSION")
        print(json.dumps(report, indent=2)); return
    index = matches[0]
    ledger = load_ledger(args.ledger)
    position = hypothetical_position(ledger, "CAT")
    opened = hypothetical_open_intent(ledger, "CAT")
    def create_entry() -> bool:
        terms = entry_for_index(rows, index)
        if not terms:
            return False
        qty = whole_share_size(args.capital, terms["entry"], args.commission, .05)
        if qty < 1:
            report["action"] = "BLOCKED_INSUFFICIENT_CAPITAL"
            return False
        intent = ShadowIntent(f"cat_0168:{args.session}:BUY", "cat_0168", "CAT", "BUY",
                              str(args.session), terms["entry"], qty, qty * terms["entry"],
                              args.commission, metadata=terms)
        if append_once(args.ledger, intent): report["created"].append(intent.__dict__)
        report["action"] = "BUY"
        same_bar = bracket_exit(rows[index], terms["stop"], terms["target"])
        if same_bar:
            kind, price = same_bar
            sell = ShadowIntent(f"cat_0168:{args.session}:SELL:{kind}", "cat_0168", "CAT",
                                "SELL", str(args.session), price, qty, qty * price,
                                args.commission, metadata={"exit_type": kind})
            if append_once(args.ledger, sell): report["created"].append(sell.__dict__)
            report["action"] = "BUY_AND_SELL"
        return True
    if position:
        metadata = (opened or {}).get("metadata") or {}
        if not {"stop", "target"} <= set(metadata):
            raise ValueError("open CAT shadow position lacks frozen bracket")
        exit_ = bracket_exit(rows[index], float(metadata["stop"]), float(metadata["target"]))
        if exit_:
            kind, price = exit_
            intent = ShadowIntent(f"cat_0168:{args.session}:SELL:{kind}", "cat_0168", "CAT",
                                  "SELL", str(args.session), price, position, position * price,
                                  args.commission, metadata={"exit_type": kind})
            if append_once(args.ledger, intent): report["created"].append(intent.__dict__)
            report["action"] = "SELL"
            # Frozen SQ ordering permits a same-open re-entry only after a gap
            # exit. Intraday exits cannot be followed by an open entry.
            if kind.endswith("GAP") and create_entry():
                report["action"] = "SELL_AND_" + report["action"]
        else:
            report["action"] = "HOLD"
    else:
        create_entry()
    sync_csv(args.ledger)
    report["csv_ledger"] = str(args.ledger.with_suffix(".csv"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
