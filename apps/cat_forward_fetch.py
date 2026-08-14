#!/usr/bin/env python3
"""Fetch a recent CAT D1 window for forward shadow signals, never research."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import tempfile
from pathlib import Path


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False,
                                     prefix="." + path.name) as stream:
        temp = Path(stream.name); stream.write(content); stream.flush(); os.fsync(stream.fileno())
    temp.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", default="CAT")
    ap.add_argument("--lookback-days", type=int, default=180)
    ap.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--output", type=Path, default=Path("data/forward/CAT_CANONICAL_D1.csv"))
    ap.add_argument("--receipt", type=Path, default=Path("data/forward/CAT_CANONICAL_D1.receipt.json"))
    args = ap.parse_args()
    if args.lookback_days < 90 or args.lookback_days > 370:
        raise ValueError("forward lookback must be 90..370 days")
    import yfinance as yf
    start, end = args.as_of - dt.timedelta(days=args.lookback_days), args.as_of + dt.timedelta(days=1)
    frame = yf.download(args.ticker, start=start.isoformat(), end=end.isoformat(),
                        auto_adjust=False, actions=False, progress=False)
    if frame.empty:
        raise RuntimeError("no forward CAT data")
    lines = ["date,open,high,low,close,volume"]
    for stamp, row in frame.iterrows():
        def value(key: str) -> float:
            return float(row[(key, args.ticker)] if (key, args.ticker) in row.index else row[key])
        opening, high, low, close = (value(key) for key in ("Open", "High", "Low", "Close"))
        if low > min(opening, close) or high < max(opening, close) or low > high:
            raise ValueError(f"invalid source OHLC on {stamp.date()}")
        lines.append(f"{stamp.date()},{opening:.8f},{high:.8f},{low:.8f},{close:.8f},{value('Volume'):.0f}")
    content = "\n".join(lines) + "\n"
    atomic_text(args.output, content)
    receipt = {"schema_version": 1, "classification": "FORWARD_ONLY_NOT_RESEARCH",
               "ticker": args.ticker, "provider": "Yahoo Finance via yfinance",
               "requested_start": start.isoformat(), "requested_end_exclusive": end.isoformat(),
               "first_session": lines[1].split(",")[0], "last_session": lines[-1].split(",")[0],
               "sessions": len(lines) - 1, "csv_sha256": hashlib.sha256(content.encode()).hexdigest(),
               "performance_calculated": False, "strategy_parameters_mutable": False,
               "orders_sent": 0, "paper_authorized": False, "live_authorized": False}
    atomic_text(args.receipt, json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
