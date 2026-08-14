#!/usr/bin/env python3
"""Deterministic Wolfpack council aggregation and aggressive paper sizing."""

from __future__ import annotations

import math
import statistics


DECISIONS = {"ENTER_PAPER", "WAIT", "REJECT"}
SIDES = {"LONG": 1, "SHORT": -1}


def _finite(value, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def aggregate_council(reviews: list[dict]) -> dict:
    """Require three unanimous, internally consistent model reviews."""
    if len(reviews) != 3:
        return {"decision": "NO_SIGNAL", "reason": "exactly three model reviews required"}
    if any(row.get("decision") not in DECISIONS for row in reviews):
        return {"decision": "NO_SIGNAL", "reason": "invalid model decision"}
    if any(row["decision"] == "REJECT" for row in reviews):
        return {"decision": "REJECT", "reason": "one or more council models rejected"}
    if any(row["decision"] != "ENTER_PAPER" for row in reviews):
        return {"decision": "WAIT", "reason": "council is not unanimous"}
    directions = {row.get("direction") for row in reviews}
    if len(directions) != 1 or next(iter(directions)) not in SIDES:
        return {"decision": "REJECT", "reason": "council direction mismatch"}
    required = ("entry", "invalidation", "target", "expiry", "expected_net_gain_usdc",
                "maximum_loss_usdc")
    if any(any(row.get(key) is None for key in required) for row in reviews):
        return {"decision": "WAIT", "reason": "required execution field missing"}
    confidence = min(_finite(row.get("confidence", 0), "confidence") for row in reviews)
    return {"decision": "ENTER_PAPER", "direction": directions.pop(),
            "council_confidence": max(0.0, min(1.0, confidence)),
            "model_expected_net_gain_usdc": min(
                _finite(row["expected_net_gain_usdc"], "expected gain") for row in reviews),
            "model_maximum_loss_usdc": max(
                _finite(row["maximum_loss_usdc"], "maximum loss") for row in reviews)}


def size_position(*, equity_usdc: float, confidence: float, entry: float,
                  invalidation: float, stress_cost_bps: float,
                  collateral_usdc: float = 50.0, venue_max_leverage: float,
                  minimum_notional_usdc: float = 5.0,
                  safe_liquidation_leverage: float) -> dict:
    """Size from maximum loss first; leverage is an output, never an input target."""
    equity = _finite(equity_usdc, "equity")
    entry = _finite(entry, "entry")
    invalidation = _finite(invalidation, "invalidation")
    confidence = max(0.0, min(1.0, _finite(confidence, "confidence")))
    if equity <= 0 or entry <= 0 or invalidation <= 0:
        raise ValueError("equity and prices must be positive")
    stop_fraction = abs(entry - invalidation) / entry
    cost_fraction = _finite(stress_cost_bps, "stress cost") / 10_000
    total_loss_fraction = stop_fraction + cost_fraction
    # Aggressive paper ladder: confidence opens 1%, 2%, then 3%; never interpolate leverage.
    risk_pct = 0.01 if confidence < 0.67 else (0.02 if confidence < 0.85 else 0.03)
    risk_usdc = equity * risk_pct
    collateral = min(_finite(collateral_usdc, "collateral"), equity * 0.20)
    raw_notional = risk_usdc / total_loss_fraction
    leverage_cap = min(5.0, _finite(venue_max_leverage, "venue leverage"),
                       _finite(safe_liquidation_leverage, "safe leverage"))
    notional = min(raw_notional, collateral * leverage_cap)
    leverage = notional / collateral if collateral else 0.0
    maximum_loss = notional * total_loss_fraction
    blockers = []
    if notional < minimum_notional_usdc:
        blockers.append("notional below venue minimum")
    if stop_fraction <= cost_fraction:
        blockers.append("stop distance does not dominate stressed execution costs")
    return {"decision": "ENTER_PAPER" if not blockers else "NO_SIGNAL",
            "risk_pct": 100 * risk_pct, "risk_budget_usdc": risk_usdc,
            "collateral_usdc": collateral, "notional_usdc": notional,
            "leverage": leverage, "maximum_loss_usdc": maximum_loss,
            "stop_distance_pct": 100 * stop_fraction,
            "stress_cost_bps": stress_cost_bps, "blockers": blockers,
            "live_trading_authorized": False}


def global_signal(*, titular_votes: list[dict], council_reviews: list[dict],
                  execution: dict, equity_usdc: float = 500.0) -> dict:
    """Combine independent titular votes, three-model review and deterministic risk."""
    eligible = [row for row in titular_votes if row.get("status") == "TITULAR"]
    if len(eligible) < 2:
        return {"decision": "NO_SIGNAL", "reason": "fewer than two titulars",
                "live_trading_authorized": False}
    weights = [_finite(row.get("evidence_weight", 0), "evidence weight") for row in eligible]
    if sum(weights) <= 0:
        return {"decision": "NO_SIGNAL", "reason": "no positive evidence weight",
                "live_trading_authorized": False}
    vote = sum(weight * SIDES.get(row.get("direction"), 0)
               for weight, row in zip(weights, eligible)) / sum(weights)
    if abs(vote) < 0.67:
        return {"decision": "NO_SIGNAL", "reason": "titular consensus below 67 percent",
                "consensus": vote, "live_trading_authorized": False}
    direction = "LONG" if vote > 0 else "SHORT"
    council = aggregate_council(council_reviews)
    if council.get("decision") != "ENTER_PAPER" or council.get("direction") != direction:
        return {**council, "consensus": vote, "live_trading_authorized": False}
    sizing = size_position(
        equity_usdc=equity_usdc, confidence=council["council_confidence"],
        entry=execution["entry"], invalidation=execution["invalidation"],
        stress_cost_bps=execution["stress_cost_bps"],
        collateral_usdc=execution.get("collateral_usdc", 50),
        venue_max_leverage=execution["venue_max_leverage"],
        minimum_notional_usdc=execution.get("minimum_notional_usdc", 5),
        safe_liquidation_leverage=execution["safe_liquidation_leverage"])
    if sizing["decision"] != "ENTER_PAPER":
        return {**sizing, "consensus": vote, "direction": direction}
    expected_return = statistics.fmean(
        _finite(row["expected_net_return"], "expected net return") for row in eligible)
    expected_gain = sizing["notional_usdc"] * expected_return
    reward_risk = expected_gain / sizing["maximum_loss_usdc"] if sizing["maximum_loss_usdc"] else 0
    if expected_gain <= 0 or reward_risk < 1.5:
        return {**sizing, "decision": "NO_SIGNAL", "reason": "net reward/risk below 1.5",
                "expected_net_gain_usdc": expected_gain, "reward_risk": reward_risk,
                "consensus": vote, "direction": direction}
    return {**sizing, "decision": "ENTER_PAPER", "direction": direction,
            "consensus": vote, "expected_net_gain_usdc": expected_gain,
            "reward_risk": reward_risk, "entry": execution["entry"],
            "invalidation": execution["invalidation"], "target": execution["target"],
            "monitor_until": execution["expiry"], "live_trading_authorized": False}
