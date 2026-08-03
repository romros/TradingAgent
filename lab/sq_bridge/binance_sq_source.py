#!/usr/bin/env python3
"""Build a checksummed, UTC SQ import CSV from official Binance archives."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


BASE_URL = "https://data.binance.vision/data/spot/monthly/klines"
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def timestamp_ms(raw: str) -> int:
    value = int(raw)
    if value >= 10**15:  # Binance spot archives use microseconds from 2025-01-01.
        value //= 1000
    if value < 10**12 or value >= 10**14:
        raise ValueError(f"UNSUPPORTED_TIMESTAMP_UNIT:{raw}")
    return value


def parse_archive(content: bytes) -> list[tuple[int, str, str, str, str, str]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != 1:
            raise ValueError("ARCHIVE_MUST_CONTAIN_ONE_CSV")
        rows = []
        with archive.open(names[0]) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8"))
            for fields in reader:
                if len(fields) < 7:
                    raise ValueError("KLINE_ROW_TOO_SHORT")
                ts = timestamp_ms(fields[0])
                opened, high, low, close, volume = fields[1:6]
                values = tuple(float(value) for value in (opened, high, low, close))
                if ts % 60_000 or min(values) <= 0 or values[1] < max(values[0], values[3]) or values[2] > min(values[0], values[3]):
                    raise ValueError(f"INVALID_KLINE:{fields[0]}")
                rows.append((ts, opened, high, low, close, volume))
    return rows


def checksum_value(content: bytes) -> str:
    parts = content.decode().strip().split()
    if not parts or len(parts[0]) != 64:
        raise ValueError("INVALID_CHECKSUM_FILE")
    return parts[0].lower()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "TradingAgent-Alquimia/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def build(symbol: str, months: list[str], archive_dir: Path, output_csv: Path) -> dict:
    archive_dir.mkdir(parents=True, exist_ok=True)
    all_rows = []; sources = []
    for month in months:
        filename = f"{symbol}-1m-{month}.zip"
        url = f"{BASE_URL}/{symbol}/1m/{filename}"
        archive_path, checksum_path = archive_dir / filename, archive_dir / f"{filename}.CHECKSUM"
        if not archive_path.exists(): archive_path.write_bytes(download(url))
        if not checksum_path.exists(): checksum_path.write_bytes(download(url + ".CHECKSUM"))
        content = archive_path.read_bytes(); expected = checksum_value(checksum_path.read_bytes())
        actual = sha256(content)
        if actual != expected:
            raise ValueError(f"CHECKSUM_MISMATCH:{filename}")
        rows = parse_archive(content); all_rows.extend(rows)
        sources.append({"month": month, "url": url, "archive": str(archive_path),
                        "sha256": actual, "rows": len(rows)})
    all_rows.sort(key=lambda row: row[0])
    timestamps = [row[0] for row in all_rows]
    if len(timestamps) != len(set(timestamps)): raise ValueError("DUPLICATE_MINUTES_ACROSS_ARCHIVES")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as handle:
        # SQ's MetaTrader4 bar importer expects Date,Time,OHLCV without a
        # header. The tracked manifest supplies the schema explicitly.
        writer = csv.writer(handle)
        for ts, opened, high, low, close, volume in all_rows:
            moment = datetime.fromtimestamp(ts / 1000, timezone.utc)
            writer.writerow([moment.strftime("%Y.%m.%d"), moment.strftime("%H:%M"), opened, high, low, close, volume])
    return {
        "schema_version": 1, "source": "Binance official public spot monthly klines",
        "source_documentation": "https://github.com/binance/binance-public-data/blob/master/README.md",
        "symbol": symbol, "timeframe": "M1", "timezone": "UTC", "timestamp_units_normalized": ["milliseconds", "microseconds"],
        "sources": sources, "rows": len(all_rows),
        "first_utc": datetime.fromtimestamp(timestamps[0] / 1000, timezone.utc).isoformat() if timestamps else None,
        "last_utc": datetime.fromtimestamp(timestamps[-1] / 1000, timezone.utc).isoformat() if timestamps else None,
        "output_csv": str(output_csv), "output_sha256": sha256(output_csv.read_bytes()),
        "sq_import_format": "MetaTrader4 bar format", "sq_import_has_header": False,
        "intended_sq_symbol": f"{symbol}_BINANCE_M1", "existing_sq_symbol_overwritten": False,
        "research_authorized": False, "paper_or_live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--month", action="append", required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.symbol.upper(), args.month, args.archive_dir, args.output_csv)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
