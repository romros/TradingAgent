#!/usr/bin/env python3
"""Validate official Cboe VIX-family CSV files and emit a reproducible manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


URLS = {
    "VIX": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
    "VIX9D": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX9D_History.csv",
    "VIX3M": "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv",
}


def inspect_csv(path: Path, symbol: str) -> dict:
    raw = path.read_bytes()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    dates = []
    invalid_ohlc = 0
    invalid_ohlc_development = 0
    for row in rows:
        day = datetime.strptime(row["DATE"].strip(), "%m/%d/%Y").date()
        dates.append(day)
        open_, high, low, close = (float(row[key]) for key in ("OPEN", "HIGH", "LOW", "CLOSE"))
        if min(open_, high, low, close) <= 0 or high < max(open_, close) or low > min(open_, close):
            invalid_ohlc += 1
            if 2012 <= day.year <= 2018:
                invalid_ohlc_development += 1
    unique_dates = set(dates)
    development = [day for day in dates if 2012 <= day.year <= 2018]
    result = {
        "symbol": symbol,
        "source_url": URLS[symbol],
        "file": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": len(rows),
        "first_date": min(dates).isoformat() if dates else None,
        "last_date": max(dates).isoformat() if dates else None,
        "duplicate_dates": len(dates) - len(unique_dates),
        "invalid_ohlc_total": invalid_ohlc,
        "invalid_ohlc_development": invalid_ohlc_development,
        "development_2012_2018_rows": len(development),
    }
    result["gate"] = "PASS" if (
        rows and result["first_date"] <= "2012-01-03"
        and result["last_date"] >= "2018-12-31"
        and result["duplicate_dates"] == 0 and invalid_ohlc_development == 0
    ) else "FAIL"
    return result


def build_manifest(root: Path) -> dict:
    series = [inspect_csv(root / f"{symbol}_History.csv", symbol) for symbol in URLS]
    return {
        "schema_version": 1,
        "authority": "Cboe official historical volatility index CSV endpoints",
        "purpose": "external volatility-regime research input; not a tradable Ostium price",
        "development": "2012-01-01/2018-12-31",
        "series": series,
        "gate": "PASS" if all(row["gate"] == "PASS" for row in series) else "FAIL",
        "performance_accessed": False,
        "spx_validation_accessed": False,
        "spx_holdout_accessed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"gate": manifest["gate"], "series": [
        {key: row[key] for key in ("symbol", "rows", "first_date", "last_date", "development_2012_2018_rows", "gate")}
        for row in manifest["series"]
    ]}, indent=2))


if __name__ == "__main__":
    main()
