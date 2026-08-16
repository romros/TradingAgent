#!/usr/bin/env python3
"""Untuned chronological confirmation of the published-style Connors RSI(2) rule."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from connors_rsi2_screen_v1 import metrics, trades

HERE = Path(__file__).resolve().parent
SPEC = HERE / "connors_rsi2_recent_confirmation_preregistration_v1.json"
LOCK = HERE / "connors_rsi2_recent_confirmation_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, end: date) -> list[tuple[date, float, float]]:
    rows = []
    with path.open(newline="") as stream:
        first = stream.readline()
        stream.seek(0)
        if first.lower().startswith("date,"):
            for row in csv.DictReader(stream):
                stamp = date.fromisoformat(row["date"])
                if stamp <= end:
                    rows.append((stamp, float(row["open"]), float(row["close"])))
        else:
            for raw in stream:
                if not raw.strip():
                    continue
                fields = raw.split(",")
                stamp = date.fromisoformat(fields[0].replace(".", "-"))
                if stamp <= end:
                    rows.append((stamp, float(fields[2]), float(fields[5])))
    if len(rows) != len({row[0] for row in rows}):
        raise ValueError(f"duplicate dates: {path}")
    return sorted(rows)


def subset(items: list[dict], start: date, end: date) -> list[dict]:
    return [item for item in items if start <= item["entry"] and item["exit"] <= end]


def screen(paths: dict[str, Path]) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"]:
        raise ValueError("preregistration lock mismatch")
    if set(paths) != set(spec["assets"]):
        raise ValueError("frozen asset universe required")
    start, end = map(date.fromisoformat, spec["confirmation_period"])
    year_start, year_end = map(date.fromisoformat, spec["complete_year_gate"])
    all_trades = {asset: subset(trades(load(path, end)), start, end) for asset, path in paths.items()}
    combined = sorted((item for values in all_trades.values() for item in values), key=lambda item: item["exit"])
    year = subset(combined, year_start, year_end)
    combined_metrics = metrics(combined)
    year_metrics = metrics(year)
    by_asset = {asset: metrics(values) for asset, values in all_trades.items()}
    positive_assets = sum(value.get("total_return", 0) > 0 for value in by_asset.values())
    gates = spec["gates"]
    passed = (
        combined_metrics["trades"] >= gates["minimum_combined_trades"]
        and combined_metrics["mean_return"] > gates["combined_mean_return_strictly_above"]
        and (combined_metrics["profit_factor"] or 0) >= gates["combined_profit_factor_at_least"]
        and year_metrics.get("mean_return", -1) > gates["year_2025_mean_return_strictly_above"]
        and positive_assets >= gates["minimum_positive_assets"]
        and combined_metrics["max_drawdown"] <= gates["maximum_gross_drawdown"]
    )
    return {
        "schema_version": 1,
        "decision": "PASS_RECENT_CONFIRMATION" if passed else "REJECT_RECENT_CONFIRMATION",
        "preregistration_sha256": sha(SPEC),
        "optimized": False,
        "maximum_market_date_accessed": str(end),
        "combined": combined_metrics,
        "year_2025": year_metrics,
        "by_asset": by_asset,
        "positive_assets": positive_assets,
        "small_account_cost_gate_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = {name: Path(path) for name, path in (item.split("=", 1) for item in args.asset)}
    result = screen(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
