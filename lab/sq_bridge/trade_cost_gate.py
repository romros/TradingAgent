#!/usr/bin/env python3
"""Porta reproduible de costos, risc i Monte Carlo sobre ordres de SQ."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from datetime import datetime
from pathlib import Path


def _number(value: str) -> float:
    """Parse SQ CSV numbers exported with either decimal dot or comma."""
    return float(value.strip().replace(" ", "").replace(",", "."))


def _nearest_rank(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("No hi ha observacions")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def load_orders(path: Path, contract_multiplier: float = 1.0) -> list[dict[str, float]]:
    if contract_multiplier <= 0:
        raise ValueError("contract_multiplier ha de ser positiu")
    rows: list[dict[str, float]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            price, size = _number(row["Open price"]), _number(row["Size"])
            exposure = price * size * contract_multiplier
            if exposure <= 0:
                raise ValueError("Open price * Size ha de ser positiu")
            opened = datetime.strptime(row["Open time"], "%Y.%m.%d %H:%M:%S") if row.get("Open time") else None
            closed = datetime.strptime(row["Close time"], "%Y.%m.%d %H:%M:%S") if row.get("Close time") else None
            held_years = (closed - opened).total_seconds() / (365.25 * 86400) if opened and closed else 0.0
            if held_years < 0:
                raise ValueError("Close time anterior a Open time")
            rows.append({
                "return": _number(row["Profit/Loss"]) / exposure,
                "mae": abs(_number(row["MAE ($)"])) / exposure,
                "pnl": _number(row["Profit/Loss"]),
                "exposure": exposure,
                "held_years": held_years,
            })
    if not rows:
        raise ValueError(f"CSV sense ordres: {path}")
    return rows


def validate_contract_units(path: Path, contract_multiplier: float) -> None:
    """Reject the common SQ FX-lot/unit mismatch before it can produce a verdict."""
    header = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:2]
    if any("EURUSD" in line for line in header) and contract_multiplier == 1:
        raise ValueError("EURUSD SQ exporta Size en lots; indica --contract-multiplier 100000")


def _metrics_pnls(pnls: list[float]) -> dict:
    gains = sum(value for value in pnls if value > 0)
    losses = -sum(value for value in pnls if value < 0)
    balance = peak = max_drawdown = 0.0
    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
    return {
        "trades": len(pnls),
        "net_pnl_usdc": round(sum(pnls), 8),
        "net_expectancy_usdc": round(sum(pnls) / len(pnls), 8),
        "net_profit_factor": round(gains / losses, 8) if losses else None,
        "win_rate": round(sum(value > 0 for value in pnls) / len(pnls), 8),
        "max_drawdown_usdc": round(max_drawdown, 8),
    }


def _metrics(net_returns: list[float], notional: float) -> dict:
    return _metrics_pnls([value * notional for value in net_returns])


def _monte_carlo_pnls(pnls: list[float], runs: int, seed: int) -> dict:
    rng = random.Random(seed)
    totals, drawdowns = [], []
    for _ in range(runs):
        metrics = _metrics_pnls([rng.choice(pnls) for _ in pnls])
        totals.append(metrics["net_pnl_usdc"])
        drawdowns.append(metrics["max_drawdown_usdc"])
    return {
        "runs": runs,
        "seed": seed,
        "profitable_ratio": round(sum(value > 0 for value in totals) / runs, 8),
        "p05_net_pnl_usdc": round(_nearest_rank(totals, 0.05), 8),
        "p95_max_drawdown_usdc": round(_nearest_rank(drawdowns, 0.95), 8),
    }


def evaluate(path: Path, methodology: dict, scenarios: list[dict], *, broker_max_leverage: float,
             venue_max_leverage: float, contract_multiplier: float = 1.0,
             source_equity: float | None = None, seed: int = 20260801) -> dict:
    validate_contract_units(path, contract_multiplier)
    orders = load_orders(path, contract_multiplier)
    account = methodology["small_account"]
    robust = methodology["robustness"]
    equity = float(account["canonical_capital_usdc"])
    risk_budget = equity * float(account["maximum_risk_per_trade_pct"]) / 100
    maes = [row["mae"] for row in orders]
    mae99 = _nearest_rank(maes, 0.99)
    risk_notional = risk_budget / mae99
    # Proxy conservador mentre no implementem la formula exacta de liquidacio d'Ostium:
    # distancia 1/L com a minim 1.5 vegades el MAE99 observat.
    strategy_proxy_cap = math.floor(1 / (mae99 * 1.5))
    hard_cap = min(broker_max_leverage, venue_max_leverage, strategy_proxy_cap)
    grid = [float(value) for value in account["leverage_grid"] if float(value) <= hard_cap]
    leverage = max(grid, default=None)
    margin_cap = equity * float(account["maximum_portfolio_margin_pct"]) / 100
    margin_notional = margin_cap * leverage if leverage else 0.0
    if source_equity is not None:
        if source_equity <= 0:
            raise ValueError("source_equity ha de ser positiu")
        base_scale = equity / source_equity
        max_scaled_exposure = max(row["exposure"] * base_scale for row in orders)
        # Preserve relative SQ sizing, but never let that bypass either the
        # MAE-derived risk cap or the portfolio-margin cap.
        allowed_notional = min(risk_notional, margin_notional)
        risk_and_margin_scale = min(1.0, allowed_notional / max_scaled_exposure) if max_scaled_exposure else 0.0
        order_scale = base_scale * risk_and_margin_scale
        notional = max(row["exposure"] * order_scale for row in orders)
        sizing_mode = "PRESERVE_SQ_RISK_SIZING"
    else:
        order_scale = None
        notional = min(risk_notional, margin_notional)
        sizing_mode = "CONSTANT_NOTIONAL"
    scenario_results = []
    for scenario in scenarios:
        proportional_cost = float(scenario["roundtrip_bps"]) / 10_000
        annual_rollover = float(scenario.get("annual_rollover_pct", 0)) / 100
        fixed_cost = float(scenario.get("fixed_cost_usdc", 0))
        if order_scale is None:
            fixed_return_cost = fixed_cost / notional if notional else float("inf")
            net_pnls = [(row["return"] - proportional_cost - annual_rollover * row["held_years"]
                         - fixed_return_cost) * notional
                        for row in orders]
        else:
            net_pnls = [row["pnl"] * order_scale
                        - row["exposure"] * order_scale * proportional_cost
                        - row["exposure"] * order_scale * annual_rollover * row["held_years"]
                        - fixed_cost for row in orders]
        metrics = _metrics_pnls(net_pnls)
        monte_carlo = _monte_carlo_pnls(net_pnls, int(robust["monte_carlo_runs"]), seed)
        checks = {
            "minimum_expectancy": metrics["net_expectancy_usdc"] >= account["minimum_net_expectancy_usdc"],
            "minimum_profit_factor": (metrics["net_profit_factor"] or float("inf")) >= account["minimum_net_profit_factor"],
            "monte_carlo_profitable": monte_carlo["profitable_ratio"] >= robust["minimum_profitable_monte_carlo_ratio"],
        }
        scenario_results.append({"name": scenario["name"], "assumptions": scenario,
                                 "metrics": metrics, "monte_carlo": monte_carlo,
                                 "passed": all(checks.values()), "checks": checks})
    base_pass = bool(scenario_results and scenario_results[0]["passed"])
    stress_pass = bool(scenario_results and scenario_results[-1]["passed"])
    verdict = "ROBUST_SMALL_ACCOUNT_CANDIDATE" if stress_pass else (
        "BASE_ONLY_NOT_ROBUST" if base_pass else "NOT_VIABLE_SMALL_ACCOUNT")
    return {
        "schema_version": 1,
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "orders": len(orders), "contract_multiplier": contract_multiplier,
        "sizing": {
            "equity_usdc": equity, "risk_budget_usdc": risk_budget,
            "mae99_pct": round(mae99 * 100, 8), "risk_notional_usdc": round(risk_notional, 8),
            "margin_notional_usdc": round(margin_notional, 8), "selected_notional_usdc": round(notional, 8),
            "selected_leverage": leverage, "hard_leverage_cap": hard_cap,
            "sizing_mode": sizing_mode, "source_equity_usdc": source_equity,
            "order_scale": round(order_scale, 10) if order_scale is not None else None,
            "liquidation_model": "CONSERVATIVE_PROXY_1_OVER_L_GTE_1_5_X_HISTORICAL_MAE99",
            "exact_ostium_liquidation_confirmation_required": True,
        },
        "scenarios": scenario_results,
        "verdict": verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v1.json"))
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--broker-max-leverage", type=float, required=True)
    parser.add_argument("--venue-max-leverage", type=float, required=True)
    parser.add_argument("--contract-multiplier", type=float, default=1.0)
    parser.add_argument("--source-equity", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.orders, json.loads(args.methodology.read_text()),
                      json.loads(args.scenarios.read_text()),
                      broker_max_leverage=args.broker_max_leverage,
                      venue_max_leverage=args.venue_max_leverage,
                      contract_multiplier=args.contract_multiplier, source_equity=args.source_equity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": result["verdict"], "sizing": result["sizing"],
                      "scenarios": [{"name": row["name"], "passed": row["passed"],
                                     "metrics": row["metrics"]} for row in result["scenarios"]]}, indent=2))


if __name__ == "__main__":
    main()
