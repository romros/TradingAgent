#!/usr/bin/env python3
"""Frozen observable next-open test of the Turnaround Tuesday hypothesis."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = HERE / "turnaround_tuesday_preregistration_v1.json"
LOCK = HERE / "turnaround_tuesday_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_spec() -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if (spec["status"] != "FROZEN_BEFORE_PERFORMANCE"
            or sha(SPEC) != lock["preregistration_sha256"]
            or lock["oos_2024_accessed"] is not False):
        raise ValueError("preregistration lock mismatch")
    return spec


def load_prices(path: Path, *, allow_oos: bool) -> list[dict]:
    if "2025" in path.name:
        raise ValueError("2025 filename refused")
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.reader(handle):
            if not raw or raw[0].lower() == "date":
                continue
            day = raw[0].replace(".", "-")
            if day > ("2024-12-31" if allow_oos else "2023-12-31"):
                continue
            offset = 2 if len(raw) >= 7 and ":" in raw[1] else 1
            rows.append({"date": day, "open": float(raw[offset]),
                         "close": float(raw[offset + 3])})
    rows.sort(key=lambda row: row["date"])
    return rows


def trades(rows: list[dict], start: str, end: str, cost_bps: float) -> list[dict]:
    result = []
    for index in range(1, len(rows) - 2):
        signal = rows[index]
        current = date.fromisoformat(signal["date"])
        previous = date.fromisoformat(rows[index - 1]["date"])
        if current.isocalendar()[:2] == previous.isocalendar()[:2]:
            continue
        entry, exit_row = rows[index + 1], rows[index + 2]
        if not (start <= entry["date"] <= end) or signal["close"] >= rows[index - 1]["close"]:
            continue
        net_return = exit_row["open"] / entry["open"] - 1 - cost_bps / 10_000
        result.append({"signal": signal["date"], "entry": entry["date"],
                       "exit": exit_row["date"], "net_return": net_return})
    return result


def metrics(rows: list[dict]) -> dict:
    equity = peak = 1.0
    drawdown = 0.0
    wins = losses = 0.0
    years: dict[str, float] = {}
    for row in rows:
        value = row["net_return"]
        equity *= 1 + value
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        wins += max(value, 0)
        losses += max(-value, 0)
        year = row["entry"][:4]
        years[year] = years.get(year, 1.0) * (1 + value)
    values = [row["net_return"] for row in rows]
    average = sum(values) / len(values) if values else None
    variance = (sum((value - average) ** 2 for value in values) / len(values)
                if values and average is not None else None)
    return {
        "trades": len(rows), "net_return": equity - 1,
        "profit_factor": wins / losses if losses else None,
        "maximum_drawdown": drawdown,
        "mean_trade_return": average,
        "t_stat": (average / math.sqrt(variance / len(values))
                   if variance and values else None),
        "calendar_year_returns": {year: value - 1 for year, value in sorted(years.items())},
        "positive_calendar_years": sum(value > 1 for value in years.values()),
    }


def passes_validation(value: dict, gate: dict) -> bool:
    return bool(
        value["trades"] >= gate["minimum_trades"]
        and value["profit_factor"] is not None
        and value["profit_factor"] >= gate["minimum_profit_factor"]
        and value["net_return"] > gate["minimum_net_return"]
        and value["positive_calendar_years"] >= gate["positive_calendar_years_required"]
        and value["maximum_drawdown"] <= gate["maximum_drawdown"]
    )


def screen(source: Path) -> dict:
    spec = load_spec()
    periods = spec["periods"]
    pre_oos = load_prices(source, allow_oos=False)
    train = metrics(trades(pre_oos, *periods["train"], spec["costs_roundtrip_bps"]))
    validation = metrics(trades(pre_oos, *periods["validation"], spec["costs_roundtrip_bps"]))
    passed = passes_validation(validation, spec["validation_gate"])
    result = {
        "schema_version": 1, "campaign_id": spec["campaign_id"],
        "preregistration_sha256": sha(SPEC), "source_sha256": sha(source),
        "costs_roundtrip_bps": spec["costs_roundtrip_bps"],
        "train": train, "validation": validation,
        "validation_gate_passed": passed,
        "decision": "PASS_VALIDATION_OPEN_OOS" if passed else "REJECT_VALIDATION",
        "oos_2024_accessed": False, "holdout_2025_accessed": False,
        "optimized": False, "paper_authorized": False, "live_authorized": False,
    }
    if passed:
        all_rows = load_prices(source, allow_oos=True)
        result["oos"] = metrics(trades(all_rows, *periods["oos"], spec["costs_roundtrip_bps"]))
        result["oos_2024_accessed"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = screen(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
