#!/usr/bin/env python3
"""Derive a fail-closed Ostium paper entry from a verified Alquimia package."""
from __future__ import annotations

import json
import math
from pathlib import Path

from lab.sq_bridge.paper_package_artifact_v4 import verify_package
from lab.sq_bridge.small_account_artifact_v4 import (
    cost_buffered_liquidation_distance_pct, select_cost_envelope,
)


def _number(value: object, label: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(f"{label} invalid")
    return float(value)


def size_entry(*, config_path: Path, equity_usdc: float,
               initial_stop_distance_pct: float, side: str,
               maximum_holding_days: float) -> dict:
    """Size one inert paper instruction; this function never sends an order."""
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text())
    if not verify_package(config, config_path):
        raise ValueError("paquet paper Alquimia invalid")
    equity = _number(equity_usdc, "equity")
    stop_pct = _number(initial_stop_distance_pct, "stop inicial")
    holding_days = _number(maximum_holding_days, "holding maxim")
    if equity <= 0 or stop_pct <= 0 or holding_days < 0 or side not in {"long", "short"}:
        raise ValueError("entrada paper fora del domini")
    base = config_path.parent
    cost_path = (base / config["cost_model_path"]).resolve()
    costs = json.loads(cost_path.read_text())
    risk_pct = _number(config["risk_per_trade_pct"], "risc")
    risk_fraction = _number(config["risk_per_trade_fraction"], "fraccio de risc")
    if (config.get("risk_unit") != "percentage_points_in_risk_per_trade_pct"
            or config.get("stop_distance_unit") != "percentage_points"
            or not math.isclose(risk_fraction, risk_pct / 100.0)):
        raise ValueError("unitats de sizing paper inconsistents")
    risk_budget = equity * risk_fraction
    uncapped_notional = risk_budget / (stop_pct / 100.0)
    maximum = _number(config["maximum_position_notional_usdc"], "nocional maxim")
    minimum = max(
        _number(config["minimum_position_notional_usdc"], "nocional minim validat"),
        _number(config["venue_minimum_notional_usdc"], "nocional minim Ostium"))
    notional = min(uncapped_notional, maximum)
    if notional < minimum:
        raise ValueError("nocional runtime per sota de l'envolupant validada")
    leverage = _number(config["selected_leverage"], "leverage")
    venue_max = _number(config["venue_max_leverage"], "leverage maxim Ostium")
    bucket, variable, fixed, carry = select_cost_envelope(costs, notional)
    stress_cost = notional * variable["stress"] / 10_000 + fixed["stress"]
    stress_bps = variable["stress"] + fixed["stress"] / notional * 10_000
    annual = _number(
        (carry.get(side) or {}).get("stress_annual_cost_pct"), "carry stress")
    collateral = notional / leverage
    committed = collateral + stress_cost
    margin_pct = collateral / equity * 100
    reserve = equity - committed
    reserve_pct = reserve / equity * 100
    liquidation_distance = cost_buffered_liquidation_distance_pct(
        leverage, venue_max, stress_bps, annual, holding_days)
    buffer = liquidation_distance / stop_pct
    reasons = []
    if leverage > venue_max:
        reasons.append("leverage_above_venue_limit")
    if margin_pct > _number(
            config["maximum_portfolio_margin_pct_policy"], "limit de marge"):
        reasons.append("portfolio_margin_above_limit")
    if reserve_pct < _number(config["minimum_reserve_pct_policy"], "limit de reserva"):
        reasons.append("reserve_below_limit")
    if buffer < _number(
            config["minimum_stop_to_liquidation_buffer_ratio_policy"],
            "buffer minim"):
        reasons.append("liquidation_buffer_below_limit")
    if reasons:
        raise ValueError("ordre paper no segura: " + ";".join(reasons))
    actual_risk = notional * stop_pct / 100.0
    return {
        "schema_version": 1, "decision": "PASS_PAPER_ENTRY_SIZING",
        "order_sent": False, "candidate_id": config["candidate_id"],
        "ostium_pair_id": config["ostium_pair_id"], "side": side,
        "equity_usdc": equity, "risk_budget_usdc": risk_budget,
        "actual_stop_risk_usdc": actual_risk,
        "initial_stop_distance_pct": stop_pct,
        "uncapped_position_notional_usdc": uncapped_notional,
        "position_notional_usdc": notional,
        "notional_capped": notional < uncapped_notional,
        "cost_notional_bucket_usdc": bucket,
        "stress_entry_cost_usdc": stress_cost,
        "selected_leverage": leverage, "collateral_usdc": collateral,
        "capital_committed_usdc": committed,
        "portfolio_margin_pct": margin_pct,
        "reserve_usdc": reserve, "reserve_pct": reserve_pct,
        "cost_buffered_liquidation_distance_pct": liquidation_distance,
        "stop_to_liquidation_buffer_ratio": buffer,
    }
