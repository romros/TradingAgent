#!/usr/bin/env python3
"""Evaluate the preregistered MSFT 0.14 SQ-native neighborhood."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.ibkr_equity_small_account_audit_v2 import load_orders, simulate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _locked(path: Path, lock: Path) -> dict:
    value = json.loads(path.read_text())
    if json.loads(lock.read_text()).get("sha256") != _sha(path):
        raise ValueError(f"lock mismatch: {path}")
    return value


def _passes(metrics: dict, gate: dict, *, include_quarters: bool) -> bool:
    result = (metrics["trades"] >= gate.get("minimum_trades_each_segment", 0)
              and (metrics["profit_factor"] or 0) >= gate["minimum_profit_factor_each_segment"]
              and metrics["return_pct"] > gate["minimum_return_pct_each_segment_exclusive"]
              and metrics["maximum_drawdown_pct_close_to_close"]
              <= gate["maximum_drawdown_pct_each_segment"])
    if include_quarters:
        result = result and metrics["positive_quarters"] / metrics["quarters"] >= (
            gate["minimum_positive_quarter_ratio_each_segment"])
    return result


def evaluate(preregistration: Path, preregistration_lock: Path,
             contract_path: Path, contract_lock: Path,
             validation_dir: Path, oos_dir: Path) -> dict:
    prereg = _locked(preregistration, preregistration_lock)
    contract = _locked(contract_path, contract_lock)
    variants = prereg["variants"]
    if len(variants) != 27 or contract["capital_usd"] != 1000:
        raise ValueError("frozen neighborhood contract invalid")
    rows = []
    for variant in variants:
        identity = variant["id"]
        stages = {}
        for stage, root in (("validation", validation_dir), ("oos", oos_dir)):
            path = root / f"orders-{stage}-{identity}.csv"
            if not path.is_file():
                raise ValueError(f"orders missing: {path}")
            orders = load_orders(path, allow_same_bar_d1=True)
            stages[stage] = {
                plan: simulate(orders, initial_capital=1000, plan=plan)
                for plan in ("tiered", "stress")}
            stages[stage]["orders_csv_sha256"] = _sha(path)
        tiered_pass = all(_passes(stages[stage]["tiered"],
                                  contract["per_variant_tiered_gate"],
                                  include_quarters=True)
                          for stage in ("validation", "oos"))
        stress_pass = all(_passes(stages[stage]["stress"],
                                  contract["per_variant_stress_diagnostic"],
                                  include_quarters=False)
                          for stage in ("validation", "oos"))
        rows.append({**variant, "stages": stages, "tiered_pass": tiered_pass,
                     "stress_pass": stress_pass})
    tiered = [row for row in rows if row["tiered_pass"]]
    stress = [row for row in rows if row["stress_pass"]]
    levels = {
        "rising_bars": sorted({row["bars"] for row in tiered}),
        "stop_pct": sorted({row["stop_pct"] for row in tiered}),
        "target_atr20": sorted({row["target_atr"] for row in tiered}),
    }
    expected = prereg["dimensions"]
    coverage = (levels["rising_bars"] == expected["rising_bars"]
                and levels["stop_pct"] == expected["stop_pct"]
                and levels["target_atr20"] == expected["target_atr20"])
    region = contract["region_gate"]
    passed = (len(tiered) >= region["minimum_tiered_pass_variants_of_27"]
              and len(stress) >= region["minimum_stress_pass_variants_of_27"]
              and (coverage or not region["every_axis_level_must_have_a_tiered_pass"]))
    medoid = None
    if passed:
        medoid = min(tiered, key=lambda row: (
            abs(row["bars"] - 4) + abs(row["stop_pct"] - 1.4) / .2
            + abs(row["target_atr"] - 4.4) / .4, row["id"]))["id"]
    return {
        "schema_version": 1,
        "decision": "PASS_ROBUST_REGION" if passed else "REJECT_FRAGILE_REGION",
        "preregistration_sha256": _sha(preregistration),
        "evaluation_contract_sha256": _sha(contract_path),
        "tiered_pass_count": len(tiered),
        "stress_pass_count": len(stress),
        "tiered_axis_coverage": levels,
        "axis_coverage_pass": coverage,
        "selected_medoid": medoid,
        "holdout_accessed": False,
        "library_admitted": False,
        "variants": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--validation-orders", type=Path, required=True)
    parser.add_argument("--oos-orders", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.root / "neighborhood_preregistration.json",
        args.root / "neighborhood_preregistration.lock.json",
        args.root / "evaluation_contract.json",
        args.root / "evaluation_contract.lock.json",
        args.validation_orders, args.oos_orders)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "decision", "tiered_pass_count", "stress_pass_count",
        "tiered_axis_coverage", "axis_coverage_pass", "selected_medoid")}, indent=2))


if __name__ == "__main__":
    main()
