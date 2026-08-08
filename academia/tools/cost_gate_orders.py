#!/usr/bin/env python3
"""Cheap small-account cost gate for StrategyQuant order CSV exports."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


SCENARIOS = (
    {"name": "base", "roundtrip_bps": 4.5, "fixed_cost_usdc": 0.1, "annual_rollover_pct": 4},
    {"name": "conservative", "roundtrip_bps": 7, "fixed_cost_usdc": 0.1, "annual_rollover_pct": 8},
    {"name": "stress", "roundtrip_bps": 10, "fixed_cost_usdc": 0.1, "annual_rollover_pct": 12},
)


def number(value: str) -> float:
    return float(value.strip().replace(" ", "").replace(",", "."))


def nearest_rank(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("orders CSV has no rows")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def load_orders(path: Path, contract_multiplier: float) -> list[dict[str, float]]:
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            exposure = number(row["Open price"]) * number(row["Size"]) * contract_multiplier
            if exposure <= 0:
                raise ValueError("non-positive exposure")
            opened = datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S")
            closed = datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S")
            held_years = (closed - opened).total_seconds() / (365.25 * 86400)
            if held_years < 0:
                raise ValueError("negative holding period")
            rows.append({
                "pnl": number(row["Profit/Loss"]),
                "exposure": exposure,
                "mae": abs(number(row["MAE ($)"])) / exposure,
                "held_years": held_years,
            })
    if not rows:
        raise ValueError("orders CSV has no rows")
    return rows


def metrics(pnls: list[float]) -> dict:
    gains = sum(value for value in pnls if value > 0)
    losses = -sum(value for value in pnls if value < 0)
    balance = peak = drawdown = 0.0
    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    return {
        "trades": len(pnls),
        "net_pnl_usdc": round(sum(pnls), 8),
        "net_expectancy_usdc": round(sum(pnls) / len(pnls), 8),
        "net_profit_factor": round(gains / losses, 8) if losses else None,
        "max_drawdown_usdc": round(drawdown, 8),
    }


def evaluate(path: Path, *, equity: float = 500, risk_pct: float = 1,
             max_effective_leverage: float = 5, source_equity: float = 10_000,
             contract_multiplier: float = 100_000) -> dict:
    orders = load_orders(path, contract_multiplier)
    mae99 = nearest_rank([row["mae"] for row in orders], 0.99)
    risk_notional = equity * risk_pct / 100 / mae99
    leverage_notional = equity * max_effective_leverage
    base_scale = equity / source_equity
    max_scaled_exposure = max(row["exposure"] * base_scale for row in orders)
    allowed_notional = min(risk_notional, leverage_notional)
    order_scale = base_scale * min(1.0, allowed_notional / max_scaled_exposure)
    selected_notional = max(row["exposure"] * order_scale for row in orders)

    scenario_results = []
    for scenario in SCENARIOS:
        proportional = scenario["roundtrip_bps"] / 10_000
        annual_rollover = scenario["annual_rollover_pct"] / 100
        pnls = [
            row["pnl"] * order_scale
            - row["exposure"] * order_scale * proportional
            - row["exposure"] * order_scale * annual_rollover * row["held_years"]
            - scenario["fixed_cost_usdc"]
            for row in orders
        ]
        result_metrics = metrics(pnls)
        passed = (
            result_metrics["net_expectancy_usdc"] > 0
            and (result_metrics["net_profit_factor"] or float("inf")) >= 1.10
        )
        scenario_results.append({"name": scenario["name"], "assumptions": scenario,
                                 "metrics": result_metrics, "passed": passed})
    return {
        "schema_version": 1,
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sizing": {
            "equity_usdc": equity, "risk_pct": risk_pct,
            "mae99_pct": round(mae99 * 100, 8),
            "risk_notional_usdc": round(risk_notional, 8),
            "leverage_notional_cap_usdc": round(leverage_notional, 8),
            "selected_notional_usdc": round(selected_notional, 8),
            "order_scale": round(order_scale, 10),
            "max_effective_leverage": max_effective_leverage,
        },
        "scenarios": scenario_results,
        "passed_base": scenario_results[0]["passed"],
        "passed_stress": scenario_results[-1]["passed"],
        "verdict": "CHEAP_COST_PASS" if scenario_results[0]["passed"] else "CHEAP_COST_FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("orders", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = [evaluate(path) for path in args.orders]
    summary = {
        "schema_version": 1,
        "evaluated": len(results),
        "base_passed": sum(item["passed_base"] for item in results),
        "stress_passed": sum(item["passed_stress"] for item in results),
        "results": results,
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
