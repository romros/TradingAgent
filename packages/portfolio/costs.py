"""Revaloració auditable dels trades paper sota escenaris de cost nominals."""
from __future__ import annotations

from typing import Any, Mapping

from packages.shared import config


def configured_scenarios() -> dict[str, float]:
    return {
        "base": config.PAPER_COST_BPS,
        "conservative": config.PAPER_COST_CONSERVATIVE_BPS,
        "stress": config.PAPER_COST_STRESS_BPS,
    }


def gross_pnl(trade: Mapping[str, Any]) -> float:
    """PnL abans de costos, reconstruït de camps immutables del trade."""
    if bool(trade.get("liq_triggered")):
        return -float(trade["collateral"])

    entry = trade.get("entry_price")
    exit_ = trade.get("exit_price")
    nominal = trade.get("nominal")
    if entry is not None and exit_ is not None and nominal is not None and float(entry) > 0:
        return float(nominal) * (float(exit_) - float(entry)) / float(entry)

    recorded_pnl = trade.get("pnl")
    recorded_fee = trade.get("fee")
    if recorded_pnl is None:
        raise ValueError("settled trade without prices or recorded pnl")
    return float(recorded_pnl) + float(recorded_fee or 0.0)


def analyse_trade(
    trade: Mapping[str, Any], scenarios: Mapping[str, float] | None = None
) -> dict[str, Any]:
    scenarios = dict(scenarios or configured_scenarios())
    gross = gross_pnl(trade)
    nominal = float(trade.get("nominal") or 0.0)
    estimates = {}
    for name, bps in scenarios.items():
        cost = nominal * float(bps) / 10_000.0
        estimates[name] = {
            "bps": float(bps),
            "cost": cost,
            "pnl": gross - cost,
        }
    return {
        "gross_pnl": gross,
        "recorded_fee": float(trade.get("fee") or 0.0),
        "recorded_pnl": float(trade.get("pnl") or 0.0),
        "scenarios": estimates,
    }


def summarise_trades(
    trades: list[Mapping[str, Any]], scenarios: Mapping[str, float] | None = None
) -> dict[str, Any]:
    scenarios = dict(scenarios or configured_scenarios())
    analysed = [analyse_trade(t, scenarios) for t in trades]
    result = {
        "model": "nominal_bps_reestimated",
        "gross_pnl_total": sum(x["gross_pnl"] for x in analysed),
        "recorded_fee_total": sum(x["recorded_fee"] for x in analysed),
        "recorded_pnl_total": sum(x["recorded_pnl"] for x in analysed),
        "scenarios": {},
    }
    for name, bps in scenarios.items():
        pnls = [x["scenarios"][name]["pnl"] for x in analysed]
        costs = [x["scenarios"][name]["cost"] for x in analysed]
        result["scenarios"][name] = {
            "bps": float(bps),
            "cost_total": sum(costs),
            "pnl_total": sum(pnls),
            "avg_pnl_per_trade": sum(pnls) / len(pnls) if pnls else None,
            "wins": sum(p > 0 for p in pnls),
            "losses": sum(p <= 0 for p in pnls),
        }
    return result
