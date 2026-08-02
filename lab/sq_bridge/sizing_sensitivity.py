#!/usr/bin/env python3
"""Sensitivity-only sizing study; never changes the preregistered risk gate."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from trade_cost_gate import evaluate, load_orders


def study(orders_path: Path, methodology: dict, scenarios: list[dict], risk_grid: list[float],
          leverage_grid: list[float], contract_multiplier: float, source_equity: float,
          broker_max_leverage: float, venue_max_leverage: float) -> dict:
    orders = load_orders(orders_path, contract_multiplier)
    rows = []
    for risk_pct in risk_grid:
        candidate_methodology = copy.deepcopy(methodology)
        candidate_methodology["small_account"]["maximum_risk_per_trade_pct"] = risk_pct
        result = evaluate(orders_path, candidate_methodology, scenarios,
                          broker_max_leverage=broker_max_leverage,
                          venue_max_leverage=venue_max_leverage,
                          contract_multiplier=contract_multiplier,
                          source_equity=source_equity)
        leverage = result["sizing"]["selected_leverage"]
        maes = [row["mae"] for row in orders]
        liq = {str(int(level) if level.is_integer() else level): {
                   "threshold_pct": round(100 / level, 8),
                   "events": sum(mae >= 1 / level for mae in maes),
                   "event_ratio": round(sum(mae >= 1 / level for mae in maes) / len(maes), 8)}
               for level in leverage_grid if level <= min(broker_max_leverage, venue_max_leverage)}
        rows.append({"risk_per_trade_pct": risk_pct, "sizing": result["sizing"],
                     "verdict": result["verdict"], "scenarios": result["scenarios"],
                     "liquidation_proxy_by_leverage": liq,
                     "selected_leverage_liquidation_proxy": liq.get(str(int(leverage))) if leverage else None})
    return {"schema_version": 1, "purpose": "SENSITIVITY_NOT_GATE_OVERRIDE",
            "preregistered_risk_pct": methodology["small_account"]["maximum_risk_per_trade_pct"],
            "orders": len(orders), "max_mae_pct": round(max(row["mae"] for row in orders) * 100, 8),
            "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--methodology", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--risk-grid", default="1,2,3")
    parser.add_argument("--leverage-grid", default="10,15,20,25,30,50")
    parser.add_argument("--contract-multiplier", type=float, default=1)
    parser.add_argument("--source-equity", type=float, required=True)
    parser.add_argument("--broker-max-leverage", type=float, required=True)
    parser.add_argument("--venue-max-leverage", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = study(args.orders, json.loads(args.methodology.read_text()),
                   json.loads(args.scenarios.read_text()),
                   [float(x) for x in args.risk_grid.split(",")],
                   [float(x) for x in args.leverage_grid.split(",")],
                   args.contract_multiplier, args.source_equity,
                   args.broker_max_leverage, args.venue_max_leverage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"max_mae_pct": result["max_mae_pct"], "rows": [{
        "risk_per_trade_pct": row["risk_per_trade_pct"], "verdict": row["verdict"],
        "selected_notional_usdc": row["sizing"]["selected_notional_usdc"],
        "selected_leverage": row["sizing"]["selected_leverage"],
        "selected_leverage_liquidation_proxy": row["selected_leverage_liquidation_proxy"],
        "scenarios": [{"name": s["name"], "passed": s["passed"], "metrics": s["metrics"]}
                      for s in row["scenarios"]]} for row in result["rows"]]}, indent=2))


if __name__ == "__main__":
    main()
