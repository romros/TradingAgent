#!/usr/bin/env python3
"""Pure fail-closed admission gate before a portfolio paper order is sent."""
from __future__ import annotations

import math
from typing import Any


def _number(value: object, label: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(f"{label} invalid")
    return float(value)


def admit(*, portfolio: dict[str, Any], sizing: dict[str, Any],
          active_allocations: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate one inert sizing instruction; never submits or mutates an order."""
    candidates = portfolio.get("candidate_ids")
    policy = portfolio.get("aggregate_risk_policy")
    if (portfolio.get("stage") != "portfolio_construction"
            or portfolio.get("decision") != "PASS"
            or portfolio.get("holdout_accessed") is not False
            or portfolio.get("paper_authorized") is not False
            or not isinstance(candidates, list) or not 4 <= len(candidates) <= 8
            or not isinstance(policy, dict)):
        raise ValueError("verified portfolio contract required")
    candidate = sizing.get("candidate_id")
    if (sizing.get("decision") != "PASS_PAPER_ENTRY_SIZING"
            or sizing.get("order_sent") is not False
            or candidate not in candidates):
        raise ValueError("paper sizing is not authorized by portfolio")
    equity = _number(sizing.get("equity_usdc"), "equity")
    new_risk = _number(sizing.get("actual_stop_risk_usdc"), "new stop risk")
    new_commitment = _number(sizing.get("capital_committed_usdc"),
                             "new capital commitment")
    if equity <= 0 or new_risk <= 0 or new_commitment <= 0:
        raise ValueError("paper sizing amounts outside domain")
    if not isinstance(active_allocations, list):
        raise ValueError("active allocation inventory invalid")
    ids, active_candidates, risk, commitment = [], [], 0.0, 0.0
    for row in active_allocations:
        if not isinstance(row, dict):
            raise ValueError("active allocation invalid")
        allocation_id, active_candidate = row.get("allocation_id"), row.get("candidate_id")
        if (not isinstance(allocation_id, str) or not allocation_id
                or not isinstance(active_candidate, str)
                or active_candidate not in candidates):
            raise ValueError("active allocation identity invalid")
        ids.append(allocation_id)
        active_candidates.append(active_candidate)
        risk += _number(row.get("stop_risk_usdc"), "active stop risk")
        commitment += _number(row.get("capital_commitment_usdc"),
                              "active capital commitment")
    if len(ids) != len(set(ids)):
        raise ValueError("active allocation id duplicated")
    projected_positions = len(active_allocations) + 1
    projected_risk = risk + new_risk
    projected_commitment = commitment + new_commitment
    projected_risk_pct = projected_risk / equity * 100
    projected_commitment_pct = projected_commitment / equity * 100
    reasons = []
    if candidate in active_candidates:
        reasons.append("candidate_already_active")
    if projected_positions > _number(
            policy.get("maximum_concurrent_positions"), "position limit"):
        reasons.append("concurrent_position_limit")
    if projected_risk_pct > _number(
            policy.get("maximum_concurrent_stop_risk_pct"), "risk limit") + 1e-9:
        reasons.append("aggregate_stop_risk_limit")
    if projected_commitment_pct > _number(
            policy.get("maximum_concurrent_capital_commitment_pct"),
            "commitment limit") + 1e-9:
        reasons.append("aggregate_capital_commitment_limit")
    return {
        "schema_version": 1,
        "decision": ("PASS_PORTFOLIO_ENTRY_ADMISSION" if not reasons
                     else "BLOCK_PORTFOLIO_ENTRY_ADMISSION"),
        "candidate_id": candidate, "order_sent": False,
        "equity_usdc": equity,
        "new_stop_risk_usdc": new_risk,
        "new_capital_commitment_usdc": new_commitment,
        "active_positions": len(active_allocations),
        "active_allocation_ids": sorted(ids),
        "projected_positions": projected_positions,
        "projected_stop_risk_usdc": projected_risk,
        "projected_stop_risk_pct": projected_risk_pct,
        "projected_capital_commitment_usdc": projected_commitment,
        "projected_capital_commitment_pct": projected_commitment_pct,
        "blocking_reasons": reasons, "paper_only": True,
        "live_authorized": False,
    }
