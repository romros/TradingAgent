#!/usr/bin/env python3
"""Resumable Dukascopy M1 BID archive for research-only source preparation."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import lzma
import struct
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
RECORD = struct.Struct(">IIIIIf")


def month_days(year: int, month: int) -> list[date]:
    current = date(year, month, 1)
    result = []
    while current.month == month:
        result.append(current)
        current += timedelta(days=1)
    return result


def decode(payload: bytes, symbol: str, day: date) -> list[tuple]:
    raw = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
    scale = 1_000 if "JPY" in symbol else 100_000
    epoch = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    rows = []
    for offset in range(0, len(raw) - RECORD.size + 1, RECORD.size):
        seconds, op, high, low, close, volume = RECORD.unpack_from(raw, offset)
        if op or high:
            rows.append((epoch + seconds, op/scale, high/scale, low/scale, close/scale, float(volume)))
    return rows


def fetch_day(symbol: str, day: date, timeout: int = 30, retries: int = 3) -> tuple[date, list[tuple], str | None]:
    url = f"{BASE_URL}/{symbol}/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    request = urllib.request.Request(url, headers={"User-Agent": "TradingAgent-Alquimia/1.0"})
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            return day, decode(payload, symbol, day) if payload else [], None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return day, [], None
            last_error = f"HTTP {exc.code}"
        except (OSError, lzma.LZMAError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt + 1 < retries:
            time.sleep(2 ** attempt)
    return day, [], last_error


def partition_path(root: Path, symbol: str, year: int, month: int) -> Path:
    return root / symbol / "tf=1m" / f"year={year:04d}" / f"month={month:02d}" / "data.csv.gz"


def build_month(root: Path, symbol: str, year: int, month: int, workers: int) -> dict:
    target = partition_path(root, symbol, year, month)
    manifest = target.with_name("manifest.json")
    if target.exists() and manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous.get("status") == "complete":
            return {**previous, "action": "skipped"}
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_day, symbol, day) for day in month_days(year, month)]
        for future in as_completed(futures):
            day, rows, error = future.result()
            results.extend(rows)
            if error:
                errors.append({"date": day.isoformat(), "error": error})
    results.sort(key=lambda row: row[0])
    if errors:
        return {"symbol": symbol, "year": year, "month": month, "status": "failed", "errors": errors}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp.gz")
    with gzip.open(temporary, "wt", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["ts", "open", "high", "low", "close", "volume"])
        writer.writerows(results)
    temporary.replace(target)
    receipt = {"schema_version": 1, "symbol": symbol, "year": year, "month": month,
               "status": "complete", "rows": len(results),
               "first_ts": results[0][0] if results else None, "last_ts": results[-1][0] if results else None,
               "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "source": BASE_URL,
               "downloaded_at": datetime.now(timezone.utc).isoformat(), "action": "written"}
    manifest_tmp = manifest.with_suffix(".tmp.json")
    manifest_tmp.write_text(json.dumps(receipt, indent=2) + "\n")
    manifest_tmp.replace(manifest)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--symbol", default="GBPUSD")
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True, help="Inclusive")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or args.from_year > args.to_year:
        raise SystemExit("Invalid worker or year range")
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    failed = 0
    for year in range(args.from_year, args.to_year + 1):
        for month in range(1, 13):
            receipt = build_month(args.root, args.symbol.upper(), year, month, args.workers)
            with args.journal.open("a") as stream:
                stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            print(json.dumps({k: receipt.get(k) for k in ("year", "month", "status", "rows", "action")}))
            failed += receipt.get("status") != "complete"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
