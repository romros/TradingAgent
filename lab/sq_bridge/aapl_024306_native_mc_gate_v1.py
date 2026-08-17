#!/usr/bin/env python3
"""Adjudicate AAPL 0.24306 native SQ parameter Monte Carlo payloads."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_pnls(payload: bytes) -> list[float]:
    if len(payload) < 4 or len(payload) % 4:
        raise ValueError("invalid SQ compact Monte Carlo PnL payload")
    values = struct.unpack(f">{len(payload) // 4}i", payload)
    count, raw = values[0], values[1:]
    if count < 0 or count != len(raw):
        raise ValueError("SQ compact Monte Carlo trade count mismatch")
    return [value / 100 for value in raw]


def csv_pnls(path: Path) -> list[float]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [float(row["Profit/Loss"].replace(",", "."))
                for row in csv.DictReader(handle, delimiter=";")]


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def evaluate(sqx: Path, original_orders: Path, gate_path: Path) -> dict:
    gate = json.loads(gate_path.read_text())
    with zipfile.ZipFile(sqx) as archive:
        names = archive.namelist()
        original_name = next(name for name in names
                             if name.endswith("/RobustnessOriginalOrders.bin"))
        simulation_names = sorted(
            (name for name in names if "/MonteCarloRetest_Simulation" in name
             and name.endswith("Orders.bin")),
            key=lambda name: int(name.rsplit("Simulation", 1)[1].split("Orders", 1)[0]),
        )
        original = compact_pnls(archive.read(original_name))
        simulations = [compact_pnls(archive.read(name)) for name in simulation_names]
    observed = csv_pnls(original_orders)
    if len(original) != len(observed) or any(
            abs(left - right) > 0.011 for left, right in zip(original, observed)):
        raise ValueError("native compact original does not match official SQ orders CSV")
    expected = gate["experiment"]["simulations"]
    if len(simulations) + 1 != expected:
        raise ValueError("native Monte Carlo simulation count mismatch")
    initial_balance = 10_000.0
    returns = [sum(run) / initial_balance for run in [original, *simulations]]
    metrics = {
        "simulations": len(returns),
        "profitable_simulation_ratio": sum(value > 0 for value in returns) / len(returns),
        "median_total_return": percentile(returns, .5),
        "p05_total_return": percentile(returns, .05),
        "zero_trade_simulation_ratio": (
            sum(not run for run in [original, *simulations]) / len(returns)
        ),
        "minimum_total_return": min(returns),
        "maximum_total_return": max(returns),
        "median_trade_count": percentile(
            [float(len(run)) for run in [original, *simulations]], .5),
    }
    threshold = gate["decision_gate"]
    checks = {
        "profitable_ratio": metrics["profitable_simulation_ratio"]
            >= threshold["minimum_profitable_simulation_ratio"],
        "median_return": metrics["median_total_return"]
            >= threshold["minimum_median_total_return"],
        "p05_return": metrics["p05_total_return"]
            >= threshold["minimum_p05_total_return"],
        "zero_trade_ratio": metrics["zero_trade_simulation_ratio"]
            <= threshold["maximum_zero_trade_simulation_ratio"],
    }
    return {
        "schema_version": 1,
        "decision": "PASS_NATIVE_PARAMETER_MONTE_CARLO" if all(checks.values())
                    else "REJECT_NATIVE_PARAMETER_MONTE_CARLO",
        "candidate_id": gate["candidate_id"],
        "sqx_path": str(sqx.resolve()),
        "sqx_sha256": sha256(sqx),
        "official_original_orders_path": str(original_orders.resolve()),
        "official_original_orders_sha256": sha256(original_orders),
        "preregistered_gate_path": str(gate_path.resolve()),
        "preregistered_gate_sha256": sha256(gate_path),
        "compact_payload_semantics": "big_endian int32 trade_count followed by signed PnL cents",
        "original_payload_matches_official_orders_csv": True,
        "metrics": metrics,
        "checks": checks,
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--original-orders", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.sqx, args.original_orders, args.gate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], **result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
