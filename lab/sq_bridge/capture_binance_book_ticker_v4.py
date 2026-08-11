#!/usr/bin/env python3
"""Capture one timestamped Binance spot book ticker as mapping evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


BASE_URL = "https://api.binance.com/api/v3/ticker/bookTicker"


def normalize(payload: dict[str, Any], symbol: str, captured_at: str) -> dict[str, Any]:
    if payload.get("symbol") != symbol:
        raise ValueError("Binance ticker symbol mismatch")
    try:
        bid, ask = Decimal(str(payload["bidPrice"])), Decimal(str(payload["askPrice"]))
    except (KeyError, InvalidOperation) as exc:
        raise ValueError("invalid Binance ticker") from exc
    if bid <= 0 or ask < bid:
        raise ValueError("invalid Binance bid/ask")
    mid = (bid + ask) / 2
    return {
        "schema_version": 1, "captured_at": captured_at,
        "source": {"provider": "Binance", "market": "spot",
                   "endpoint": BASE_URL, "symbol": symbol},
        "quote": {"bid": float(bid), "ask": float(ask), "mid": float(mid)},
        "raw_payload_sha256": hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "performance_accessed": False,
    }


def capture(symbol: str, timeout: float = 15) -> dict[str, Any]:
    url = f"{BASE_URL}?{urllib.parse.urlencode({'symbol': symbol})}"
    request = urllib.request.Request(url, headers={"User-Agent": "Alquimia-v4/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return normalize(payload, symbol, datetime.now(timezone.utc).isoformat())


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, choices=("BTCUSDT", "ETHUSDT"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture(args.symbol)
    write_atomic(args.output.resolve(), result)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
