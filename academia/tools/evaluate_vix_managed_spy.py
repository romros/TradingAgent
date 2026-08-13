#!/usr/bin/env python3
"""Evaluate the frozen weekly VIX-managed SPY rule without touching holdout data."""

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_yahoo_chart(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"]["adjclose"][0]["adjclose"]
    rows = []
    for index, timestamp in enumerate(result["timestamp"]):
        close = quote["close"][index]
        open_price = quote["open"][index]
        adjusted_close = adjusted[index]
        if None in (close, open_price, adjusted_close) or close <= 0:
            continue
        rows.append({
            "date": datetime.utcfromtimestamp(timestamp).date().isoformat(),
            "adjusted_open": open_price * adjusted_close / close,
        })
    return rows


def load_vix(path: Path) -> dict[str, float]:
    values = {}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            day = datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat()
            values[day] = float(row["CLOSE"])
    return values


def build_weekly_periods(prices: list[dict], vix: dict[str, float]) -> list[dict]:
    weekly = []
    seen = set()
    vix_days = sorted(vix)
    vix_index = 0
    latest_prior = None
    for row in prices:
        day = datetime.fromisoformat(row["date"]).date()
        key = day.isocalendar()[:2]
        while vix_index < len(vix_days) and vix_days[vix_index] < row["date"]:
            latest_prior = vix[vix_days[vix_index]]
            vix_index += 1
        if key in seen:
            continue
        seen.add(key)
        if latest_prior is None or latest_prior <= 0:
            continue
        weekly.append({
            "date": row["date"],
            "adjusted_open": row["adjusted_open"],
            "prior_vix": latest_prior,
            "exposure": min(1.0, 20.0 / latest_prior),
        })
    periods = []
    for current, following in zip(weekly, weekly[1:]):
        periods.append({**current, "return": following["adjusted_open"] / current["adjusted_open"] - 1})
    return periods


def _metrics(periods: list[dict], managed: bool, roundtrip_bps: float,
             annual_carry_pct: float) -> dict:
    equity = peak = 1.0
    maximum_drawdown = 0.0
    previous_exposure = 0.0
    yearly = {}
    for row in periods:
        exposure = row["exposure"] if managed else 1.0
        turnover = abs(exposure - previous_exposure)
        # Half the measured roundtrip is charged on each one-way exposure change.
        # Carry is sampled per 8h by Ostium and frozen by the upstream cost gate.
        trading_cost = turnover * roundtrip_bps / 20_000
        carry_cost = exposure * annual_carry_pct / 100 / 52.1775
        net_return = exposure * row["return"] - trading_cost - carry_cost
        equity *= 1 + net_return
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, 1 - equity / peak)
        year = row["date"][:4]
        yearly[year] = yearly.get(year, 1.0) * (1 + net_return)
        previous_exposure = exposure
    years = max(len(periods) / 52.1775, 1 / 52.1775)
    net_return = equity - 1
    return {
        "periods": len(periods),
        "net_return_pct": 100 * net_return,
        "cagr_pct": 100 * (equity ** (1 / years) - 1),
        "maximum_drawdown_pct": 100 * maximum_drawdown,
        "return_over_drawdown": None if maximum_drawdown == 0 else net_return / maximum_drawdown,
        "positive_years": sum(value > 1 for value in yearly.values()),
        "year_count": len(yearly),
        "annual_carry_pct": annual_carry_pct,
    }


def evaluate(prices: list[dict], vix: dict[str, float], start: str, end: str,
             roundtrip_bps: float, annual_carry_pct: float) -> dict:
    periods = [row for row in build_weekly_periods(prices, vix) if start <= row["date"] <= end]
    if not periods:
        raise ValueError("no weekly periods in requested interval")
    return {
        "interval": f"{start}/{end}",
        "roundtrip_bps": roundtrip_bps,
        "managed": _metrics(periods, True, roundtrip_bps, annual_carry_pct),
        "always_long": _metrics(periods, False, roundtrip_bps, annual_carry_pct),
    }


def development_gate(result: dict) -> dict:
    managed = result["managed"]
    baseline = result["always_long"]
    checks = {
        "net_return_positive": managed["net_return_pct"] > 0,
        "drawdown_reduction_at_least_15pct": (
            managed["maximum_drawdown_pct"] <= 0.85 * baseline["maximum_drawdown_pct"]),
        "return_over_drawdown_above_baseline": (
            managed["return_over_drawdown"] is not None
            and baseline["return_over_drawdown"] is not None
            and managed["return_over_drawdown"] > baseline["return_over_drawdown"]),
        "positive_years_at_least_6_of_8": (
            managed["year_count"] == 8 and managed["positive_years"] >= 6),
    }
    return {"pass": all(checks.values()), "checks": checks}


def validation_gate(result: dict, development: dict) -> dict:
    managed = result["managed"]
    baseline = result["always_long"]
    development_ratio = development["managed"]["return_over_drawdown"]
    checks = {
        "net_return_positive": managed["net_return_pct"] > 0,
        "drawdown_below_baseline": (
            managed["maximum_drawdown_pct"] < baseline["maximum_drawdown_pct"]),
        "return_over_drawdown_at_least_80pct_of_development": (
            managed["return_over_drawdown"] is not None
            and development_ratio is not None
            and managed["return_over_drawdown"] >= 0.8 * development_ratio),
        "positive_years_at_least_3_of_5": (
            managed["year_count"] == 5 and managed["positive_years"] >= 3),
    }
    return {"pass": all(checks.values()), "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spy", required=True, type=Path)
    parser.add_argument("--vix", required=True, type=Path)
    parser.add_argument("--cost-gate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    gate = json.loads(args.cost_gate.read_text())
    if gate.get("decision") != "PASS_COSTS_FROZEN":
        raise SystemExit("execution cost is not frozen; refusing to reveal strategy results")
    prices = load_yahoo_chart(args.spy)
    vix = load_vix(args.vix)
    base_cost = float(gate["by_notional"]["200"]["base_roundtrip_bps"])
    stress_cost = float(gate["by_notional"]["200"]["stress_roundtrip_bps"])
    base_carry = float(gate["carry"]["base_annual_cost_pct"]["long"])
    stress_carry = float(gate["carry"]["stress_annual_cost_pct"]["long"])
    def scenarios(start: str, end: str) -> dict:
        return {
            "base": evaluate(prices, vix, start, end, base_cost, base_carry),
            "stress": evaluate(prices, vix, start, end, stress_cost, stress_carry),
        }
    development = scenarios("2007-01-01", "2014-12-31")
    development["gate"] = development_gate(development["base"])
    output = {
        "experiment_id": "spx-volatility-managed-equity-premium-v37",
        "data": {"spy_sha256": _sha256(args.spy), "vix_sha256": _sha256(args.vix)},
        "development": development,
        "holdout_accessed": False,
    }
    if development["gate"]["pass"]:
        validation = scenarios("2015-01-01", "2019-12-31")
        validation["gate"] = validation_gate(validation["base"], development["base"])
        output["validation"] = validation
        output["decision"] = "PASS_VALIDATION" if validation["gate"]["pass"] else "REJECT_VALIDATION"
    else:
        output["validation"] = {"status": "NOT_REVEALED_AFTER_DEVELOPMENT_FAIL"}
        output["decision"] = "REJECT_DEVELOPMENT"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
