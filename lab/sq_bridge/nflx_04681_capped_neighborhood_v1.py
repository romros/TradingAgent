#!/usr/bin/env python3
"""Risk-capped remediation diagnostic for the already observed NFLX neighborhood."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.ibkr_equity_long_short_audit_v1 import load_orders, simulate

EXPOSURE = 0.50
CAPITAL = 2000.0


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(neighborhood_path: Path, m1_receipt_path: Path) -> dict:
    neighborhood = json.loads(neighborhood_path.read_text())
    m1 = json.loads(m1_receipt_path.read_text())
    if (m1["decision"] != "PASS_STOP225_SAME_BAR_M1_FEASIBILITY"
            or m1["candidate_id"] != "NFLX04681_stop_225"):
        raise ValueError("stop225 M1 remediation absent")
    rows = []
    for prior in neighborhood["results"]:
        receipt_path = Path(prior["receipt_path"])
        receipt = json.loads(receipt_path.read_text())
        orders_path = Path(receipt["orders_csv_path"])
        orders = load_orders(orders_path, allow_same_bar_d1=True,
                             exclude_end_test=True)
        stress = simulate(orders, CAPITAL, "stress", EXPOSURE)
        checks = {
            "positive": stress["return_pct"] > 0,
            "profit_factor_at_least_1_10": (stress["profit_factor"] or 0) >= 1.10,
            "drawdown_at_most_25pct": stress["maximum_drawdown_pct_close_to_close"] <= 25,
        }
        rows.append({
            "candidate_id": prior["candidate_id"], "stress": stress,
            "checks": checks, "passed": all(checks.values()),
            "orders_sha256": sha(orders_path), "receipt_sha256": sha(receipt_path),
        })
    checks = {
        "all_ten_neighbors_executable": len(rows) == 10,
        "all_ten_neighbors_pass_capped_gate": all(row["passed"] for row in rows),
    }
    return {
        "schema_version": 1,
        "decision": "PASS_CAPPED_NEIGHBORHOOD_REMEDIATION" if all(checks.values())
                    else "REJECT_CAPPED_NEIGHBORHOOD_REMEDIATION",
        "classification": "post_observation_risk_remediation_not_original_gate_reversal",
        "exposure_fraction": EXPOSURE, "initial_capital_usd": CAPITAL,
        "source_neighborhood_sha256": sha(neighborhood_path),
        "stop225_m1_receipt_sha256": sha(m1_receipt_path),
        "checks": checks, "results": rows,
        "holdout_2025_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neighborhood", type=Path, required=True)
    parser.add_argument("--m1-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.neighborhood, args.m1_receipt)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"],
                      "results": [{"candidate": row["candidate_id"],
                                   "return_pct": row["stress"]["return_pct"],
                                   "pf": row["stress"]["profit_factor"],
                                   "dd": row["stress"]["maximum_drawdown_pct_close_to_close"]}
                                  for row in result["results"]]}, indent=2))


if __name__ == "__main__":
    main()
