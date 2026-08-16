#!/usr/bin/env python3
"""Apply the preregistered NFLX 2024 OOS gate to a frozen audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(spec_path: Path, freeze_path: Path, audit_path: Path) -> dict:
    spec = json.loads(spec_path.read_text())
    freeze = json.loads(freeze_path.read_text())
    audit = json.loads(audit_path.read_text())
    if (freeze.get("oos_accessed_before_freeze") is not False
            or audit.get("stage") != "IBKR_EQUITY_SMALL_ACCOUNT_OOS_AUDIT"
            or audit.get("candidate_id") != freeze.get("candidate_id")):
        raise ValueError("invalid frozen OOS lineage")
    gate = spec["oos_gate"]
    rows = {}
    for capital, plans in audit["results"].items():
        stress = plans["stress"]
        checks = {
            "minimum_trades": stress["trades"] >= gate["minimum_trades"],
            "minimum_stress_return": stress["return_pct"]
                > gate["minimum_stress_return_pct"],
            "minimum_stress_profit_factor": (stress["profit_factor"] or 0)
                >= gate["minimum_stress_profit_factor"],
            "maximum_drawdown": stress["maximum_drawdown_pct_close_to_close"]
                <= gate["maximum_drawdown_pct"],
        }
        rows[capital] = {"stress": stress, "checks": checks,
                         "passed": all(checks.values())}
    passing = [int(capital) for capital, row in rows.items() if row["passed"]]
    return {
        "schema_version": 1,
        "stage": "NFLX_D1_2024_OOS_GATE",
        "candidate_id": freeze["candidate_id"],
        "decision": "PASS_OOS_TO_ROBUSTNESS" if passing else "REJECT_OOS",
        "spec_sha256": sha(spec_path),
        "finalist_freeze_sha256": sha(freeze_path),
        "audit_sha256": sha(audit_path),
        "oos_gate": gate,
        "passing_capitals_usd": passing,
        "results": rows,
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--freeze", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.spec, args.freeze, args.audit)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "passing_capitals_usd": result["passing_capitals_usd"]}, indent=2))


if __name__ == "__main__":
    main()
