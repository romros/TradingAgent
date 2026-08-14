#!/usr/bin/env python3
"""Create a split-adjusted, performance-blind US-equity D1 SQ source."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, source: Path, output: Path, receipt: Path, symbol: str,
          splits: list[dict]) -> dict:
    if not source.is_file() or not splits:
        raise ValueError("source and at least one split are required")
    normalized = sorted(
        ({"effective_date": date.fromisoformat(row["effective_date"]),
          "factor": int(row["factor"]), "source_url": row["source_url"]}
         for row in splits), key=lambda row: row["effective_date"])
    if any(row["factor"] <= 1 or not row["source_url"].startswith("https://")
           for row in normalized):
        raise ValueError("each split needs factor > 1 and an HTTPS source")

    rows = []
    with source.open(newline="", encoding="utf-8-sig") as stream:
        for raw in csv.reader(stream):
            if len(raw) != 7:
                raise ValueError("expected SQ date,time,OHLC,volume rows")
            day = date.fromisoformat(raw[0].replace(".", "-"))
            values = [float(value) for value in raw[2:7]]
            cumulative = 1
            for event in normalized:
                if day < event["effective_date"]:
                    cumulative *= event["factor"]
            prices = [value / cumulative for value in values[:4]]
            volume = values[4] * cumulative
            if not (prices[1] >= max(prices[0], prices[3])
                    and prices[2] <= min(prices[0], prices[3])
                    and prices[2] > 0 and volume >= 0):
                raise ValueError(f"invalid adjusted OHLCV on {day}")
            rows.append((day, prices, volume, cumulative))
    if not rows or any(left[0] >= right[0] for left, right in zip(rows, rows[1:])):
        raise ValueError("source dates must be non-empty, unique and increasing")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        for day, prices, volume, _ in rows:
            writer.writerow([
                day.strftime("%Y.%m.%d"), "00:00",
                *(f"{value:.6f}" for value in prices), f"{volume:.6f}"])
    temporary.replace(output)

    close_jumps = []
    split_boundary_returns = []
    for previous, current in zip(rows, rows[1:]):
        change = current[1][3] / previous[1][3] - 1
        if any(current[0] == event["effective_date"] for event in normalized):
            split_boundary_returns.append({"effective_date": current[0].isoformat(),
                                           "adjusted_close_return": round(change, 9)})
        if abs(change) > .20:
            close_jumps.append({"date": current[0].isoformat(),
                                "close_return": round(change, 9)})
    result = {
        "schema_version": 1,
        "decision": "PASS_SPLIT_ADJUSTED_SOURCE_ONLY",
        "symbol": symbol,
        "timeframe": "D1",
        "adjustment_basis": "latest_share_basis",
        "source_path": str(source.resolve()),
        "source_sha256": _sha(source),
        "output_path": str(output.resolve()),
        "output_sha256": _sha(output),
        "rows": len(rows),
        "first": rows[0][0].isoformat(),
        "last": rows[-1][0].isoformat(),
        "splits": [{"effective_date": row["effective_date"].isoformat(),
                    "factor": row["factor"], "source_url": row["source_url"]}
                   for row in normalized],
        "split_boundary_returns": split_boundary_returns,
        "remaining_absolute_close_jumps_over_20pct": close_jumps,
        "performance_accessed": False,
        "oos_accessed": False,
        "holdout_accessed": False,
        "research_authorized": False,
        "paper_authorized": False,
        "live_authorized": False
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--splits", required=True, type=Path)
    args = parser.parse_args()
    events = json.loads(args.splits.read_text())
    print(json.dumps(build(source=args.source, output=args.output,
                           receipt=args.receipt, symbol=args.symbol,
                           splits=events), indent=2))


if __name__ == "__main__":
    main()
