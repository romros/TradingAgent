#!/usr/bin/env python3
"""Apply the frozen MSFT capitulation rule to one completed execution session."""
from __future__ import annotations
import argparse, csv, datetime as dt, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.execution.shadow import ShadowIntent, append_many_once, ensure_ledger, whole_share_size
from packages.strategy.capitulation_d1 import CapitulationD1Strategy


def rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        values = list(csv.DictReader(stream))
    values.sort(key=lambda x: x["date"])
    if len(values) < 21 or len({x["date"] for x in values}) != len(values):
        raise ValueError("MSFT feed needs >=21 unique ordered sessions")
    for row in values:
        o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
        if l > min(o, c) or h < max(o, c) or l > h:
            raise ValueError(f"invalid OHLC envelope on {row['date']}")
    return values


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candles", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, default=ROOT / "data/shadow/msft_capitulation.json")
    ap.add_argument("--session", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--capital", type=float, default=1000.0)
    ap.add_argument("--commission", type=float, default=1.0)
    args = ap.parse_args(); candles = rows(args.candles); ensure_ledger(args.ledger)
    index = next((i for i, x in enumerate(candles) if x["date"] == args.session.isoformat()), None)
    report = {"schema_version": 1, "mode": "shadow", "strategy": "capitulation_d1",
              "symbol": "MSFT", "session": args.session.isoformat(), "action": "NONE",
              "orders_sent": 0, "created": []}
    if index is None or index < 20:
        report["action"] = "BLOCKED_MISSING_WARMED_COMPLETED_SESSION"
        print(json.dumps(report, indent=2)); return
    signal = CapitulationD1Strategy().detect(candles[:index], asset="MSFT", mode="shadow")
    if signal is None:
        print(json.dumps(report, indent=2)); return
    execution = candles[index]; entry, exit_ = float(execution["open"]), float(execution["close"])
    qty = whole_share_size(args.capital, entry, args.commission, .05)
    if qty < 1:
        report["action"] = "BLOCKED_INSUFFICIENT_CAPITAL"
        print(json.dumps(report, indent=2)); return
    common = {"signal_session": signal.candle_date, "exit_type": "SAME_SESSION_CLOSE",
              "frozen_rule": "body<-2%; close<BB_lower(20,2,population); next open-to-close"}
    intents = [
        ShadowIntent(f"msft_capitulation:{args.session}:BUY", "capitulation_d1", "MSFT", "BUY",
                     str(args.session), entry, qty, qty * entry, args.commission, metadata=common),
        ShadowIntent(f"msft_capitulation:{args.session}:SELL:CLOSE", "capitulation_d1", "MSFT", "SELL",
                     str(args.session), exit_, qty, qty * exit_, args.commission, metadata=common),
    ]
    created = append_many_once(args.ledger, intents)
    report.update(action="BUY_AND_SELL", created=[x.__dict__ for x in intents] if created else [],
                  intents_created=created, csv_ledger=str(args.ledger.with_suffix(".csv")),
                  signal_session=signal.candle_date)
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
