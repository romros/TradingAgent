#!/usr/bin/env python3
"""Probe official Ostium OHLC coverage without persisting copyrighted price series."""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


ENDPOINT = "https://builder.prod.bedrock.ostium.io/v1/ohlc"
DEFAULT_ASSETS = {
    "EUR/USD": "EUR-USD",
    "US500/USD": "SPX-USD",
    "XAU/USD": "XAU-USD",
    "WTI/USD": "CL-USD",
    "BTC/USD": "BTC-USD",
    "TLT/USD": "TLT-USD",
}


def iso_date(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).date().isoformat()


def summarize(payload: dict, requested_start: str, requested_end: str) -> dict:
    candles = payload.get("data", [])
    if not candles:
        return {
            "count": 0,
            "first": None,
            "last": None,
            "covers_requested_start": False,
            "covers_requested_end": False,
        }
    first = iso_date(candles[0]["time"])
    last = iso_date(candles[-1]["time"])
    return {
        "count": len(candles),
        "first": first,
        "last": last,
        "covers_requested_start": first <= requested_start,
        "covers_requested_end": last >= requested_end,
    }


def fetch(pair: str, start_ts: int, end_ts: int, timeout: int = 30) -> dict:
    body = json.dumps({
        "pair": pair,
        "fromTimestampSeconds": start_ts,
        "toTimestampSeconds": end_ts,
        "resolution": "1D",
    }).encode()
    request = urllib.request.Request(
        ENDPOINT, body, {"content-type": "application/json", "user-agent": "alquimia-academia/1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def probe(start: str, end: str) -> dict:
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp())
    end_ts = int(datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp())
    assets = {}
    for display_name, api_pair in DEFAULT_ASSETS.items():
        assets[display_name] = {
            "api_pair": api_pair,
            **summarize(fetch(api_pair, start_ts, end_ts), start, end),
        }
    return {
        "source": ENDPOINT,
        "resolution": "1D",
        "requested_window": f"{start}/{end}",
        "assets": assets,
        "raw_candles_persisted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe(args.start, args.end)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
