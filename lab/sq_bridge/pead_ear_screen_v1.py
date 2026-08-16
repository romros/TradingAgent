#!/usr/bin/env python3
"""Frozen price-reaction PEAD screen using point-in-time SEC Item 2.02 events."""
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
SPEC = HERE / "pead_ear_preregistration_v1.json"
LOCK = HERE / "pead_ear_preregistration_v1.lock.json"
PREFLIGHT = ROOT / "data/ibkr_sq_v2/pead_ear_v1/sec_calendar_preflight_v1.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prices(path: Path) -> dict[date, dict[str, float]]:
    result = {}
    with path.open(newline="") as stream:
        first = stream.readline()
        stream.seek(0)
        if first.lower().startswith("date,"):
            for row in csv.DictReader(stream):
                result[date.fromisoformat(row["date"])] = {key: float(row[key]) for key in ("open", "close")}
        else:
            for raw in stream:
                if not raw.strip():
                    continue
                fields = raw.split(",")
                result[date.fromisoformat(fields[0].replace(".", "-"))] = {"open": float(fields[2]), "close": float(fields[5])}
    return result


def metrics(items: list[dict]) -> dict:
    values = [item["net_return"] for item in sorted(items, key=lambda item: (item["exit"], item["asset"]))]
    if not values:
        return {"trades": 0}
    n = len(values)
    mean = sum(values) / n
    variance = sum((value - mean) ** 2 for value in values) / (n - 1) if n > 1 else 0
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = -sum(value for value in values if value < 0)
    equity = peak = 1.0
    maximum_drawdown = 0.0
    for value in values:
        equity *= 1 + value
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, 1 - equity / peak)
    return {
        "trades": n,
        "wins": sum(value > 0 for value in values),
        "mean_net_return": mean,
        "compounded_net_return": equity - 1,
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "t_stat": mean / math.sqrt(variance / n) if variance else None,
        "maximum_drawdown": maximum_drawdown,
    }


def screen(spy_path: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    preflight = json.loads(PREFLIGHT.read_text())
    if sha(SPEC) != lock["preregistration_sha256"] or sha(PREFLIGHT) != spec["upstream_preflight_sha256"]:
        raise ValueError("frozen input hash mismatch")
    spy = prices(spy_path)
    spy_days = sorted(spy)
    spy_position = {day: index for index, day in enumerate(spy_days)}
    economics = spec["economics"]
    notional = float(economics["reference_notional_usd_per_event"])
    all_items = []
    skipped = []
    asset_prices = {asset: prices(ROOT / details["market_path"]) for asset, details in preflight["assets"].items()}
    for event in preflight["events"]:
        asset = event["asset"]
        frame = asset_prices[asset]
        reaction = date.fromisoformat(event["reaction_session"])
        entry = date.fromisoformat(event["entry_session"])
        exit_day = date.fromisoformat(event["exit_20_session"])
        asset_days = sorted(frame)
        asset_position = {day: index for index, day in enumerate(asset_days)}
        if reaction not in asset_position or asset_position[reaction] == 0 or reaction not in spy_position or spy_position[reaction] == 0:
            skipped.append({"asset": asset, "accession": event["accession"], "reason": "reaction window unavailable"})
            continue
        prior_asset = asset_days[asset_position[reaction] - 1]
        prior_spy = spy_days[spy_position[reaction] - 1]
        ear = frame[reaction]["close"] / frame[prior_asset]["close"] - spy[reaction]["close"] / spy[prior_spy]["close"]
        if ear <= 0:
            continue
        entry_price, exit_price = frame[entry]["open"], frame[exit_day]["open"]
        shares = math.floor(notional / entry_price)
        if shares < 1:
            skipped.append({"asset": asset, "accession": event["accession"], "reason": "whole share unaffordable"})
            continue
        friction = 2 * economics["minimum_per_order_usd"] + shares * (entry_price + exit_price) * economics["bps_per_side"] / 10000
        net_pnl = shares * (exit_price - entry_price) - friction
        all_items.append({
            "asset": asset, "accession": event["accession"], "reaction": reaction,
            "entry": entry, "exit": exit_day, "ear": ear, "shares": shares,
            "net_return": net_pnl / (shares * entry_price),
        })
    periods = {}
    period_items = {}
    for name, bounds in spec["periods"].items():
        start, end = map(date.fromisoformat, bounds)
        values = [item for item in all_items if start <= item["reaction"] <= end]
        period_items[name] = values
        periods[name] = metrics(values)
    combined_items = period_items["validation"] + period_items["oos_2024"]
    combined = metrics(combined_items)
    years = {str(year): metrics([item for item in combined_items if item["reaction"].year == year]) for year in range(2022, 2025)}
    by_asset = {asset: metrics([item for item in combined_items if item["asset"] == asset]) for asset in spec["universe"]}
    positive_years = sum(value.get("mean_net_return", 0) > 0 for value in years.values())
    positive_assets = sum(value.get("mean_net_return", 0) > 0 for value in by_asset.values())
    gate = spec["gates"]
    passed = (
        periods["train"]["mean_net_return"] > gate["train_net_mean_strictly_above"]
        and periods["validation"]["mean_net_return"] > gate["validation_net_mean_strictly_above"]
        and periods["oos_2024"]["mean_net_return"] > gate["oos_net_mean_strictly_above"]
        and combined["trades"] >= gate["combined_validation_oos_minimum_trades"]
        and (combined["profit_factor"] or 0) >= gate["combined_validation_oos_profit_factor_at_least"]
        and (combined["t_stat"] or -999) >= gate["combined_validation_oos_one_sided_t_stat_at_least"]
        and positive_years >= gate["minimum_positive_years_2022_2024"]
        and positive_assets >= gate["minimum_positive_assets_validation_oos"]
        and combined["maximum_drawdown"] <= gate["maximum_combined_validation_oos_drawdown_pct"] / 100
    )
    return {
        "schema_version": 1,
        "decision": "PASS_STATISTICAL_EDGE_GATE" if passed else "REJECT_PEADEAR_GATE",
        "preregistration_sha256": sha(SPEC),
        "optimized": False,
        "periods": periods,
        "combined_validation_oos": combined,
        "years_2022_2024": years,
        "by_asset_validation_oos": by_asset,
        "positive_years": positive_years,
        "positive_assets": positive_assets,
        "signals_executed": len(all_items),
        "return_extremes": sorted(all_items, key=lambda item: item["net_return"])[:10]
        + sorted(all_items, key=lambda item: item["net_return"], reverse=True)[:10],
        "skipped": skipped,
        "portfolio_concurrency_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = screen(args.spy)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({key: result[key] for key in ("decision", "periods", "combined_validation_oos", "positive_years", "positive_assets", "signals_executed")}, indent=2))


if __name__ == "__main__":
    main()
