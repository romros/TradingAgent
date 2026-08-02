"""Deterministic capital-based risk glidepath for small accounts."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class CapitalRiskTier:
    capital_below: float
    risk_pct: float


def parse_risk_glidepath(raw: str) -> tuple[CapitalRiskTier, ...]:
    tiers = []
    for item in raw.split(","):
        if not item.strip():
            continue
        boundary_raw, risk_raw = item.split(":", 1)
        boundary = math.inf if boundary_raw.strip().lower() in {"inf", "infinity"} else float(boundary_raw)
        risk = float(risk_raw)
        if boundary <= 0 or not 0 < risk <= .05:
            raise ValueError("capital boundaries must be positive and risk must be in (0, 0.05]")
        tiers.append(CapitalRiskTier(boundary, risk))
    if not tiers or not math.isinf(tiers[-1].capital_below):
        raise ValueError("risk glidepath must end with an inf tier")
    if any(left.capital_below >= right.capital_below for left, right in zip(tiers, tiers[1:])):
        raise ValueError("risk glidepath capital boundaries must be strictly increasing")
    if any(left.risk_pct < right.risk_pct for left, right in zip(tiers, tiers[1:])):
        raise ValueError("risk must not increase as capital grows")
    return tuple(tiers)


def risk_pct_for_capital(capital: float, tiers: Iterable[CapitalRiskTier], fallback: float) -> float:
    if capital <= 0:
        raise ValueError("capital must be positive")
    for tier in tiers:
        if capital < tier.capital_below:
            return tier.risk_pct
    return fallback
