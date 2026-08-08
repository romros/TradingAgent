#!/usr/bin/env python3
"""Model determinista d'economia i liquidacio per SPX/USD a Ostium."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def liquidation_distance_pct(leverage: float, venue_max_leverage: float) -> float:
    """Distancia adversa aproximada segons la formula oficial d'Ostium."""
    if leverage <= 0 or venue_max_leverage <= 0 or leverage > venue_max_leverage:
        raise ValueError("palanquejament fora dels limits")
    loss_threshold_pct = 100.0 - leverage / venue_max_leverage * 25.0
    return loss_threshold_pct / leverage


def audit(*, capitals=(200.0, 500.0), risk_pct=1.0,
          stop_distances_pct=(1.0, 0.5, 0.25), opening_fee_bps=3.0,
          oracle_fee_usdc=0.10, venue_max_leverage=200.0,
          annual_rollover_scenarios_pct=(4.6, 5.6), holding_days=(0.25, 1.0, 5.0)) -> dict:
    rows = []
    for capital in capitals:
        risk = capital * risk_pct / 100.0
        for stop_pct in stop_distances_pct:
            notional = risk / (stop_pct / 100.0)
            leverage = notional / capital
            opening_fee = notional * opening_fee_bps / 10_000.0
            rows.append({
                "capital_usdc": capital,
                "risk_usdc": round(risk, 6),
                "stop_distance_pct": stop_pct,
                "notional_usdc": round(notional, 6),
                "collateral_if_all_capital_usdc": capital,
                "effective_leverage_if_all_capital": round(leverage, 6),
                "opening_fee_usdc": round(opening_fee, 6),
                "oracle_fee_refunded_full_close_usdc": 0.0,
                "oracle_fee_failed_or_partial_action_usdc": oracle_fee_usdc,
                "breakeven_confirmed_cost_bps": opening_fee_bps,
                "breakeven_stress_oracle_not_refunded_bps": round(
                    opening_fee_bps + oracle_fee_usdc / notional * 10_000.0, 6),
                "liquidation_distance_pct": round(
                    liquidation_distance_pct(leverage, venue_max_leverage), 6),
            })
    carry = []
    for annual_pct in annual_rollover_scenarios_pct:
        for days in holding_days:
            carry.append({
                "annual_rollover_pct": annual_pct,
                "holding_days": days,
                "cost_bps_on_notional": round(annual_pct / 100.0 * days / 365.25 * 10_000.0, 6),
            })
    return {
        "schema_version": 1,
        "instrument": "Ostium SPX/USD (UI: US500/USD)",
        "facts": {
            "opening_fee_bps": opening_fee_bps,
            "closing_fee_bps": 0.0,
            "oracle_fee_usdc": oracle_fee_usdc,
            "oracle_refund_condition": "successful full close",
            "documented_max_leverage": venue_max_leverage,
            "bid_ask_execution": True,
            "market_schedule_et": "Sunday 18:00 through Friday 17:00; daily 17:00-18:00 break",
        },
        "scenario_assumptions": {
            "risk_per_trade_pct": risk_pct,
            "annual_rollover_pct": list(annual_rollover_scenarios_pct),
            "rollover_basis": "SOFR 3.60% snapshot + documented 1-2% carry premium; not a live pair rate",
            "spread_bps": None,
            "slippage_bps": None,
        },
        "sizing_examples": rows,
        "carry_examples": carry,
        "gates": {
            "research_m15": "PASS_WITH_COST_STRESS_GRID",
            "paper": "BLOCKED",
            "live": "BLOCKED",
            "missing": [
                "normalized live getPairs minSz/minNtl/maxLeverage/overnightMaxLeverage",
                "measured bid-ask distribution by session",
                "measured slippage for intended notionals",
                "live long/short rollover rate and direction",
                "strategy stop distance and OOS MAE distribution",
            ],
        },
        "decision": "Costs can be modelled for research; no safe leverage or paper authorization exists yet.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit()
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
