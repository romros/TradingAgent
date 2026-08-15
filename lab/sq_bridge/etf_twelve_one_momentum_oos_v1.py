#!/usr/bin/env python3
"""Single-use gated 2024 OOS evaluator for frozen 12-1 ETF momentum."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from lab.sq_bridge.etf_relative_momentum_screen_v1 import load, sha
from lab.sq_bridge.etf_twelve_one_momentum_screen_v1 import (
    LOCK, SPEC, monthly_returns, one_sleeve_metrics,
)


def evaluate(assets: dict[str, Path], validation_report: Path,
             output: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    lock = json.loads(LOCK.read_text())
    prior = json.loads(validation_report.read_text())
    frozen_hash = sha(SPEC)
    if frozen_hash != lock["preregistration_sha256"]:
        raise ValueError("FROZEN_CONTRACT_MISMATCH")
    if prior["decision"] != "PASS_VALIDATION_FREEZE_BEFORE_OOS":
        raise ValueError("VALIDATION_GATE_NOT_PASSED")
    if prior["preregistration_sha256"] != frozen_hash:
        raise ValueError("VALIDATION_CONTRACT_MISMATCH")
    if prior["oos_2024_performance_accessed"]:
        raise ValueError("OOS_ALREADY_ACCESSED")
    if set(assets) != set(spec["assets"]):
        raise ValueError("ASSET_CONTRACT_MISMATCH")
    source_hashes = {name: sha(path) for name, path in assets.items()}
    if source_hashes != prior["source_sha256"]:
        raise ValueError("SOURCE_CHANGED_AFTER_VALIDATION")
    frames = {name: load(path) for name, path in assets.items()}
    parse = lambda name: tuple(map(dt.date.fromisoformat,
                                   spec["periods"][name]))
    oos = one_sleeve_metrics(monthly_returns(frames, *parse("oos_2024")))
    combined = one_sleeve_metrics(monthly_returns(
        frames, parse("validation")[0], parse("oos_2024")[1]))
    gate = spec["final_gate"]
    passed = (oos["total_return"] > gate["minimum_oos_total_return"]
              and (combined["annualized_sharpe"] or -999)
              >= gate["combined_minimum_annualized_sharpe"]
              and combined["maximum_drawdown"]
              <= gate["combined_maximum_drawdown"])
    report = {
        "schema_version": 1,
        "decision": "PASS_GROSS_OOS" if passed else "REJECT_OOS_2024",
        "preregistration_sha256": frozen_hash,
        "source_sha256": source_hashes,
        "oos_2024": oos,
        "validation_plus_oos": combined,
        "oos_2024_performance_accessed": True,
        "holdout_2025_plus_accessed": False,
        "next_gate": "PARAMETER_NEIGHBOURHOOD_AND_COSTS" if passed else None,
        "paper_authorized": False,
        "live_authorized": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", action="append", required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets = {name: Path(path) for name, path in
              (value.split("=", 1) for value in args.asset)}
    print(json.dumps(evaluate(assets, args.validation_report, args.output),
                     indent=2))


if __name__ == "__main__":
    main()
