#!/usr/bin/env python3
from small_account import EconomicsInput, evaluate_trade, select_leverage

trade = EconomicsInput(200, 40, 1.0, 0.2, 3, 3, 2, 2, 1, gas_usdc=0.02, minimum_notional_usdc=10)
row = evaluate_trade(trade, 5)
assert row["notional_usdc"] == 200 and row["cost_usdc"] == 0.24 and row["net_pnl_usdc"] == 1.76
result = select_leverage(trade, [1, 2, 3, 5, 8, 10, 20], 100, 10, 20, 1.0, 0.10)
assert result["verdict"] == "SMALL_ACCOUNT_200_USDC_VIABLE"
assert result["hard_leverage_cap"] == 10 and result["selected"]["leverage"] == 5
too_expensive = EconomicsInput(**{**trade.__dict__, "gas_usdc": 10})
assert select_leverage(too_expensive, [1, 2, 3], 100, 10, 20, 1.0, 0.10)["verdict"] == "NOT_VIABLE_COSTS"
print("PASS: small-account economics and safe leverage")
