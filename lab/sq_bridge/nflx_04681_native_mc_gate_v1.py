#!/usr/bin/env python3
"""Decode and adjudicate the frozen NFLX native parameter Monte Carlo."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path

from lab.sq_bridge.aapl_024306_native_mc_gate_v1 import compact_pnls, percentile


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(sqx: Path, orders_path: Path, contract_path: Path,
             methodology_path: Path) -> dict:
    contract = json.loads(contract_path.read_text())
    methodology = json.loads(methodology_path.read_text())
    with zipfile.ZipFile(sqx) as archive:
        names = archive.namelist()
        original = compact_pnls(archive.read(next(
            name for name in names if name.endswith("/RobustnessOriginalOrders.bin"))))
        simulation_names = sorted(
            (name for name in names if "/MonteCarloRetest_Simulation" in name
             and name.endswith("Orders.bin")),
            key=lambda name: int(name.rsplit("Simulation", 1)[1].split("Orders", 1)[0]))
        randomized = [compact_pnls(archive.read(name)) for name in simulation_names]
    with orders_path.open(newline="", encoding="utf-8-sig") as handle:
        observed = [float(row["Profit/Loss"].replace(",", "."))
                    for row in csv.DictReader(handle, delimiter=";")]
    if len(original) != len(observed) or any(abs(a - b) > .011 for a, b in zip(original, observed)):
        raise ValueError("native original does not match official SQ orders")
    unchanged = contract["no_parameter_change_simulations"]
    if (len(randomized) != contract["randomized_simulations_materialized"]
            or unchanged + len(randomized) != methodology["robustness"]["monte_carlo_runs"]):
        raise ValueError("native MC persistence contract mismatch")
    runs = [original] * unchanged + randomized
    returns = [sum(run) / 10_000 for run in runs]
    metrics = {
        "conceptual_simulations": len(runs),
        "persisted_randomized_payloads": len(randomized),
        "unchanged_original_repetitions": unchanged,
        "profitable_simulation_ratio": sum(value > 0 for value in returns) / len(returns),
        "median_return_on_sq_10000_balance": percentile(returns, .5),
        "p05_return_on_sq_10000_balance": percentile(returns, .05),
        "minimum_return_on_sq_10000_balance": min(returns),
        "zero_trade_simulation_ratio": sum(not run for run in runs) / len(runs),
    }
    threshold = methodology["robustness"]["minimum_profitable_monte_carlo_ratio"]
    checks = {"minimum_profitable_ratio": metrics["profitable_simulation_ratio"] >= threshold,
              "all_conceptual_runs_accounted": len(runs) == 2000,
              "original_payload_matches_orders": True}
    return {
        "schema_version": 1,
        "decision": "PASS_NATIVE_PARAMETER_MONTE_CARLO" if all(checks.values())
                    else "REJECT_NATIVE_PARAMETER_MONTE_CARLO",
        "candidate_id": "Strategy 0.4681", "metrics": metrics, "checks": checks,
        "threshold_source": "frozen_methodology.robustness.minimum_profitable_monte_carlo_ratio",
        "sqx_sha256": sha(sqx), "orders_sha256": sha(orders_path),
        "contract_sha256": sha(contract_path), "methodology_sha256": sha(methodology_path),
        "holdout_2025_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqx", type=Path, required=True)
    parser.add_argument("--orders", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--methodology", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.sqx, args.orders, args.contract, args.methodology)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], **result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
