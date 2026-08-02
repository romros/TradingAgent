#!/usr/bin/env python3
"""Economia determinista i seleccio de leverage per a un compte petit."""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class EconomicsInput:
    equity_usdc: float
    collateral_usdc: float
    gross_return_pct: float
    adverse_move_pct: float
    opening_fee_bps: float
    closing_fee_bps: float
    spread_bps: float
    slippage_bps: float
    price_impact_bps: float
    rollover_usdc: float = 0.0
    gas_usdc: float = 0.0
    minimum_notional_usdc: float = 0.0

def evaluate_trade(item: EconomicsInput, leverage: float) -> dict:
    if item.equity_usdc <= 0 or item.collateral_usdc <= 0 or leverage < 1:
        raise ValueError("equity, collateral i leverage han de ser positius")
    if item.collateral_usdc > item.equity_usdc:
        raise ValueError("collateral no pot superar equity")
    notional = item.collateral_usdc * leverage
    all_bps = item.opening_fee_bps + item.closing_fee_bps + item.spread_bps + item.slippage_bps + item.price_impact_bps
    cost = notional * all_bps / 10_000 + item.rollover_usdc + item.gas_usdc
    gross_pnl = notional * item.gross_return_pct / 100
    adverse_loss = notional * item.adverse_move_pct / 100 + cost
    return {"leverage": leverage, "notional_usdc": round(notional, 8),
        "gross_pnl_usdc": round(gross_pnl, 8), "cost_usdc": round(cost, 8),
        "net_pnl_usdc": round(gross_pnl - cost, 8),
        "adverse_loss_usdc": round(adverse_loss, 8),
        "adverse_loss_equity_pct": round(adverse_loss / item.equity_usdc * 100, 8),
        "minimum_notional_ok": notional >= item.minimum_notional_usdc}

def select_leverage(item: EconomicsInput, leverage_grid: list[float], venue_max: float,
                    broker_guard_max: float, strategy_max: float, max_risk_usdc: float,
                    minimum_net_pnl_usdc: float) -> dict:
    hard_cap = min(venue_max, broker_guard_max, strategy_max)
    rows = [evaluate_trade(item, lev) for lev in leverage_grid if lev <= hard_cap]
    valid = [row for row in rows if row["minimum_notional_ok"]
             and row["adverse_loss_usdc"] <= max_risk_usdc
             and row["net_pnl_usdc"] >= minimum_net_pnl_usdc]
    selected = max(valid, key=lambda row: row["leverage"], default=None)
    if selected:
        verdict = "SMALL_ACCOUNT_200_USDC_VIABLE"
    elif rows and all(not row["minimum_notional_ok"] for row in rows):
        verdict = "NOT_VIABLE_MIN_SIZE"
    elif rows and all(row["net_pnl_usdc"] < minimum_net_pnl_usdc for row in rows):
        verdict = "NOT_VIABLE_COSTS"
    else:
        verdict = "NOT_VIABLE_RISK"
    return {"input": asdict(item), "hard_leverage_cap": hard_cap,
            "selected": selected, "verdict": verdict, "evaluations": rows}

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", help="JSON amb input, grid i limits")
    args = parser.parse_args()
    payload = json.loads(args.payload)
    print(json.dumps(select_leverage(EconomicsInput(**payload["input"]), **payload["selection"]), indent=2))

if __name__ == "__main__":
    main()
