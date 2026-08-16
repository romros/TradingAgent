#!/usr/bin/env python3
"""Frozen SPY close-to-close drift around regular scheduled FOMC statements."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = HERE / "spy_pre_fomc_drift_preregistration_v1.json"
LOCK = HERE / "spy_pre_fomc_drift_preregistration_v1.lock.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_market(path: Path) -> list[tuple[date, float]]:
    with path.open(newline="") as stream:
        return [(date.fromisoformat(row["date"]), float(row["close"])) for row in csv.DictReader(stream)]


def event_trades(market: list[tuple[date, float]], events: set[date], capital: float, order_fee: float, bps: float) -> list[dict]:
    rows = []
    for index in range(1, len(market)):
        exit_day, exit_price = market[index]
        if exit_day not in events:
            continue
        entry_day, entry_price = market[index - 1]
        shares = math.floor(capital / entry_price)
        friction = 2 * order_fee + shares * (entry_price + exit_price) * bps / 10000
        rows.append({
            "entry": entry_day,
            "exit": exit_day,
            "entry_close": entry_price,
            "exit_close": exit_price,
            "shares": shares,
            "gross_return": exit_price / entry_price - 1,
            "net_pnl": shares * (exit_price - entry_price) - friction,
        })
    return rows


def metrics(rows: list[dict], capital: float) -> dict:
    values = [row["net_pnl"] for row in rows]
    n = len(values)
    if not n:
        return {"events": 0}
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1) if n > 1 else 0
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    equity = peak = capital
    maximum_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak * 100)
    return {
        "events": n,
        "wins": sum(value > 0 for value in values),
        "net_pnl_usd": round(sum(values), 6),
        "net_return_pct_on_capital": round(sum(values) / capital * 100, 6),
        "mean_net_pnl_usd": round(mean, 6),
        "profit_factor": round(gross_profit / gross_loss, 6) if gross_loss else None,
        "t_stat": round(mean / math.sqrt(variance / n), 6) if variance else None,
        "closed_event_max_drawdown_pct": round(maximum_drawdown, 6),
    }


def in_period(rows: list[dict], start: date, end: date) -> list[dict]:
    return [row for row in rows if start <= row["exit"] <= end]


def screen(market_path: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    calendar_path = ROOT / spec["calendar_path"]
    if sha(SPEC) != lock["preregistration_sha256"] or sha(calendar_path) != lock["calendar_sha256"] or sha(market_path) != lock["market_data_sha256"]:
        raise ValueError("frozen input hash mismatch")
    calendar = json.loads(calendar_path.read_text())
    events = {date.fromisoformat(row["date"]) for row in calendar["events"] if date(2017, 1, 1) <= date.fromisoformat(row["date"]) <= date(2024, 12, 31)}
    economics = spec["economics"]
    capital = float(economics["capital_usd"])
    rows = event_trades(load_market(market_path), events, capital, economics["stress_minimum_per_order_usd"], economics["stress_bps_per_side"])
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
        "decision": "PASS_STATISTICAL_AND_SMALL_ACCOUNT_GATE" if passed else "REJECT_FOMC_DRIFT_GATE",
        "preregistration_sha256": sha(SPEC),
        "optimized": False,
        "stress_costs_applied": True,
        "periods": reports,
        "combined_validation_oos": combined,
        "years_2022_2024": years,
        "positive_years_2022_2024": positive_years,
        "event_count_expected": len(events),
        "event_count_matched": len(rows),
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("market", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = screen(args.market)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
