#!/usr/bin/env python3
"""Frozen 14:00-to-pre-14:00 SPY drift around scheduled FOMC statements."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from spy_pre_fomc_drift_screen_v1 import in_period, metrics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "spy_true_pre_fomc_intraday_preregistration_v1.json"
LOCK = HERE / "spy_true_pre_fomc_intraday_preregistration_v1.lock.json"
CALENDAR = HERE / "evidence/fomc_regular_statement_calendar_2015_2026.json"
NY = ZoneInfo("America/New_York")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sessions(cache_root: Path) -> dict[date, dict[time, float]]:
    sessions = {}
    for path in sorted(cache_root.glob("year=*/month=*/day=*.csv.gz")):
        local_rows = {}
        with gzip.open(path, "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                local = datetime.fromtimestamp(int(row["ts"]), timezone.utc).astimezone(NY)
                if time(9, 30) <= local.time() <= time(15, 59):
                    local_rows[local.time()] = float(row["close"])
        if local_rows:
            if len(local_rows) != 390:
                raise ValueError(f"non-390-minute RTH session: {path}")
            sessions[local.date()] = local_rows
    return sessions


def build_trades(sessions: dict[date, dict[time, float]], events: set[date], capital: float, order_fee: float, bps: float) -> list[dict]:
    days = sorted(sessions)
    positions = {day: index for index, day in enumerate(days)}
    rows = []
    for event in sorted(events):
        index = positions.get(event)
        if index is None or index == 0:
            continue
        entry_day = days[index - 1]
        entry_price = sessions[entry_day][time(14, 0)]
        exit_price = sessions[event][time(13, 59)]
        shares = math.floor(capital / entry_price)
        friction = 2 * order_fee + shares * (entry_price + exit_price) * bps / 10000
        rows.append({"entry": entry_day, "exit": event, "shares": shares, "net_pnl": shares * (exit_price - entry_price) - friction})
    return rows


def screen(cache_root: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    if sha(SPEC) != lock["preregistration_sha256"] or sha(CALENDAR) != lock["calendar_sha256"]:
        raise ValueError("frozen input hash mismatch")
    calendar = json.loads(CALENDAR.read_text())
    events = {date.fromisoformat(row["date"]) for row in calendar["events"] if date(2017, 1, 1) <= date.fromisoformat(row["date"]) <= date(2024, 12, 31)}
    economics = spec["economics"]
    capital = float(economics["capital_usd"])
    sessions = load_sessions(cache_root)
    rows = build_trades(sessions, events, capital, economics["stress_minimum_per_order_usd"], economics["stress_bps_per_side"])
    periods = {name: in_period(rows, *map(date.fromisoformat, bounds)) for name, bounds in spec["periods"].items()}
    reports = {name: metrics(values, capital) for name, values in periods.items()}
    validation_oos = periods["validation"] + periods["oos_2024"]
    combined = metrics(validation_oos, capital)
    years = {str(year): metrics([row for row in validation_oos if row["exit"].year == year], capital) for year in range(2022, 2025)}
    positive_years = sum(value.get("net_pnl_usd", 0) > 0 for value in years.values())
    gate = spec["gates"]
    passed = (
        reports["train"]["net_pnl_usd"] > gate["train_net_pnl_strictly_above_usd"]
        and reports["validation"]["net_pnl_usd"] > gate["validation_net_pnl_strictly_above_usd"]
        and reports["oos_2024"]["net_pnl_usd"] > gate["oos_net_pnl_strictly_above_usd"]
        and combined["events"] >= gate["combined_validation_oos_minimum_events"]
        and (combined["profit_factor"] or 0) >= gate["combined_validation_oos_profit_factor_at_least"]
        and (combined["t_stat"] or -999) >= gate["combined_validation_oos_one_sided_t_stat_at_least"]
        and positive_years >= gate["minimum_positive_years_2022_2024"]
        and combined["closed_event_max_drawdown_pct"] <= gate["maximum_combined_validation_oos_drawdown_pct"]
    )
    return {
        "schema_version": 1,
        "decision": "PASS_STATISTICAL_AND_SMALL_ACCOUNT_GATE" if passed else "REJECT_TRUE_PRE_FOMC_GATE",
        "preregistration_sha256": sha(SPEC),
        "optimized": False,
        "stress_costs_applied": True,
        "rth_sessions_validated": len(sessions),
        "event_count_expected": len(events),
        "event_count_matched": len(rows),
        "periods": reports,
        "combined_validation_oos": combined,
        "years_2022_2024": years,
        "positive_years_2022_2024": positive_years,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = screen(args.cache_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
