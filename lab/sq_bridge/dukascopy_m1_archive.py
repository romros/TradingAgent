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
from calendar import monthcalendar
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
ALLOWED_BASE_URLS = {BASE_URL, "http://www.dukascopy.com/datafeed"}
RECORD = struct.Struct(">IIIIIf")


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    days = [week[weekday] for week in monthcalendar(year, month) if week[weekday]]
    return date(year, month, days[nth - 1])


def _last_weekday(year: int, month: int, weekday: int) -> date:
    days = [week[weekday] for week in monthcalendar(year, month) if week[weekday]]
    return date(year, month, days[-1])


def _easter_sunday(year: int) -> date:
    # Gregorian computus (Anonymous Gregorian algorithm).
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f, g = (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = (h + ell - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def nyse_closed_dates(year: int) -> set[date]:
    closed = {
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter_sunday(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    for new_year in (date(year, 1, 1), date(year + 1, 1, 1)):
        observed = _observed(new_year)
        if observed.year == year:
            closed.add(observed)
    if year >= 2022:
        closed.add(_observed(date(year, 6, 19)))
    if year == 2018:
        closed.add(date(2018, 12, 5))
    return closed


def month_days(year: int, month: int) -> list[date]:
    current = date(year, month, 1)
    result = []
    while current.month == month:
        result.append(current)
        current += timedelta(days=1)
    return result


def default_price_scale(symbol: str) -> int:
    """Legacy FX-only inference; non-FX callers must pass catalog precision."""
    return 1_000 if "JPY" in symbol.upper() else 100_000


def is_fx_symbol(symbol: str) -> bool:
    currencies = {"USD", "EUR", "GBP", "AUD", "NZD", "CAD", "CHF", "JPY"}
    value = symbol.upper()
    return len(value) == 6 and value[:3] in currencies and value[3:] in currencies


def decode(payload: bytes, symbol: str, day: date,
           price_scale: int | None = None) -> list[tuple]:
    raw = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
    scale = price_scale or default_price_scale(symbol)
    if scale <= 0:
        raise ValueError("price_scale must be positive")
    epoch = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    rows = []
    for offset in range(0, len(raw) - RECORD.size + 1, RECORD.size):
        seconds, op, high, low, close, volume = RECORD.unpack_from(raw, offset)
        if op or high:
            rows.append((epoch + seconds, op/scale, high/scale, low/scale, close/scale, float(volume)))
    return rows


def fetch_day(symbol: str, day: date, timeout: int = 30, retries: int = 3,
              price_scale: int | None = None,
              base_url: str = BASE_URL) -> tuple[date, list[tuple], str | None]:
    if base_url not in ALLOWED_BASE_URLS:
        raise ValueError(f"unsupported Dukascopy endpoint: {base_url}")
    url = f"{base_url}/{symbol}/{day.year}/{day.month-1:02d}/{day.day:02d}/BID_candles_min_1.bi5"
    request = urllib.request.Request(url, headers={"User-Agent": "TradingAgent-Alquimia/1.0"})
    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            return day, decode(payload, symbol, day, price_scale) if payload else [], None
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


def daily_cache_path(root: Path, symbol: str, day: date) -> Path:
    return (root / symbol / "_daily_cache" / f"year={day.year:04d}"
            / f"month={day.month:02d}" / f"day={day.day:02d}.csv.gz")


def write_daily_cache(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.gz")
    with gzip.open(temporary, "wt", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["ts", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)
    temporary.replace(path)


def read_daily_cache(path: Path) -> list[tuple]:
    with gzip.open(path, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        required = ["ts", "open", "high", "low", "close", "volume"]
        if reader.fieldnames != required:
            raise ValueError(f"invalid daily cache header: {path}")
        return [(int(row["ts"]), float(row["open"]), float(row["high"]),
                 float(row["low"]), float(row["close"]), float(row["volume"]))
                for row in reader]


def build_month(root: Path, symbol: str, year: int, month: int, workers: int,
                price_scale: int | None = None,
                first_date: date | None = None,
                closed_dates: set[date] | None = None,
                base_url: str = BASE_URL) -> dict:
    target = partition_path(root, symbol, year, month)
    manifest = target.with_name("manifest.json")
    if target.exists() and manifest.exists():
        previous = json.loads(manifest.read_text())
        if previous.get("status") == "complete":
            return {**previous, "action": "skipped"}
    # Dukascopy's equities endpoint can answer HTTP 503 for closed weekends.
    # Never request them. Keep successful days in memory and retry only failed
    # weekdays, otherwise one transient response discards a whole good month.
    eligible = [day for day in month_days(year, month)
                if day.weekday() < 5 and day not in (closed_dates or set())
                and (first_date is None or day >= first_date)]
    rows_by_day: dict[date, list[tuple]] = {}
    for day in eligible:
        cached = daily_cache_path(root, symbol, day)
        if cached.exists():
            rows_by_day[day] = read_daily_cache(cached)
    pending = [day for day in eligible if day not in rows_by_day]
    errors_by_day: dict[date, str] = {}
    for round_index in range(3):
        errors_by_day = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fetch_day, symbol, day, 30, 2, price_scale, base_url)
                       for day in pending]
            for future in as_completed(futures):
                day, rows, error = future.result()
                if error:
                    errors_by_day[day] = error
                else:
                    rows_by_day[day] = rows
                    write_daily_cache(daily_cache_path(root, symbol, day), rows)
        pending = sorted(errors_by_day)
        if not pending:
            break
        if round_index < 2:
            time.sleep(2 ** round_index)
    results = [row for day in sorted(rows_by_day) for row in rows_by_day[day]]
    errors = [{"date": day.isoformat(), "error": errors_by_day[day]}
              for day in pending]
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
               "weekdays_requested": len(rows_by_day),
               "first_ts": results[0][0] if results else None, "last_ts": results[-1][0] if results else None,
               "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "source": base_url,
               "price_scale": price_scale or default_price_scale(symbol),
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
    parser.add_argument("--from-month", type=int, default=1)
    parser.add_argument("--to-month", type=int, default=12)
    parser.add_argument("--price-scale", type=int,
                        help="Raw integer divisor. Mandatory for non-FX assets; SQ catalog decimals=3 means 1000.")
    parser.add_argument("--first-date", type=date.fromisoformat,
                        help="Provider coverage start, YYYY-MM-DD; avoids false errors before listing.")
    parser.add_argument("--market-calendar", choices=("none", "nyse"), default="none",
                        help="Exclude official closed sessions; use nyse for US stocks/ETFs.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--base-url", choices=sorted(ALLOWED_BASE_URLS), default=BASE_URL,
                        help="Official Dukascopy endpoint; HTTP www is the low-latency fallback.")
    parser.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    if (not 1 <= args.workers <= 8 or args.from_year > args.to_year
            or not 1 <= args.from_month <= 12 or not 1 <= args.to_month <= 12
            or (args.from_year == args.to_year and args.from_month > args.to_month)
            or (args.price_scale is not None and args.price_scale <= 0)):
        raise SystemExit("Invalid worker or year range")
    if not is_fx_symbol(args.symbol) and args.price_scale is None:
        raise SystemExit("--price-scale is mandatory for non-FX assets")
    args.journal.parent.mkdir(parents=True, exist_ok=True)
    failed = 0
    for year in range(args.from_year, args.to_year + 1):
        first_month = args.from_month if year == args.from_year else 1
        last_month = args.to_month if year == args.to_year else 12
        for month in range(first_month, last_month + 1):
            receipt = build_month(args.root, args.symbol.upper(), year, month,
                                  args.workers, args.price_scale, args.first_date,
                                  nyse_closed_dates(year)
                                  if args.market_calendar == "nyse" else None,
                                  args.base_url)
            with args.journal.open("a") as stream:
                stream.write(json.dumps(receipt, sort_keys=True) + "\n")
            print(json.dumps({k: receipt.get(k) for k in ("year", "month", "status", "rows", "action")}))
            failed += receipt.get("status") != "complete"
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
