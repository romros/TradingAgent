#!/usr/bin/env python3
"""Open XLE 2024 once, only after the frozen validation release gate passed."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.xle_monthly_tsmom_screen_v1 import (
    LOCK, SPEC, load, metrics, returns, sha,
)


def evaluate(source: Path, validation: Path, output: Path,
             spec_path: Path = SPEC, lock_path: Path = LOCK) -> dict:
    spec = json.loads(spec_path.read_text())
    lock = json.loads(lock_path.read_text())
    prior = json.loads(validation.read_text())
    if (sha(spec_path) != lock["preregistration_sha256"]
            or prior.get("decision") != "PASS_VALIDATION_FREEZE_BEFORE_OOS"
            or prior.get("preregistration_sha256") != sha(spec_path)
            or prior.get("source_sha256") != sha(source)
            or prior.get("oos_2024_performance_accessed") is not False):
        raise ValueError("OOS_RELEASE_NOT_AUTHORIZED")
    rows = load(source)
    start, end = map(dt.date.fromisoformat, spec["periods"]["oos_2024"])
    validation_start, validation_end = map(
        dt.date.fromisoformat, spec["periods"]["validation"])
    results = {}
    for variant in spec["variants"]:
        identifier = variant["id"]
        oos_trades = returns(rows, variant["lookback_sessions"], start, end)
        combined = (returns(rows, variant["lookback_sessions"],
                            validation_start, validation_end) + oos_trades)
        results[identifier] = {
            "oos_2024": metrics(oos_trades, start, end),
            "combined_validation_oos": metrics(
                combined, validation_start, end),
        }
    gate = spec["final_gate"]
    central = results["M12"]["combined_validation_oos"]
    passed = (all(results[name]["oos_2024"]["total_return"] > 0
                  for name in ("M6", "M12"))
              and (central["annualized_monthly_sharpe"] or -999)
              >= gate["central_combined_minimum_sharpe"]
              and central["maximum_drawdown"]
              <= gate["central_combined_maximum_drawdown"])
    report = {"schema_version": 1,
              "decision": ("PASS_GROSS_EDGE_PENDING_COSTS_AND_SQ" if passed
                           else "REJECT_OOS_2024"),
              "preregistration_sha256": sha(spec_path),
              "validation_screen_sha256": sha(validation),
              "source_sha256": sha(source), "results": results,
              "oos_2024_performance_accessed": True,
              "holdout_2025_plus_accessed": False,
              "paper_authorized": False, "live_authorized": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=SPEC)
    parser.add_argument("--lock", type=Path, default=LOCK)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.source, args.validation, args.output,
                              args.spec, args.lock), indent=2))


if __name__ == "__main__":
    main()
