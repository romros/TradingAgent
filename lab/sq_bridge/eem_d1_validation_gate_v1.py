#!/usr/bin/env python3
"""Adjudicate frozen EEM D1 families without opening 2024."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/ibkr_sq_v2/eem_d1_simple_discovery_v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adjudicate() -> dict:
    freeze_path = BASE / "family_freeze_v1.json"
    freeze = json.loads(freeze_path.read_text())
    rows = []
    for representative in freeze["representatives"]:
        candidate = representative["candidate_id"]
        token = candidate.removeprefix("Strategy ").replace(".", "_")
        audit_path = BASE / "validation" / token / "ibkr_long_short_cost_audit.json"
        receipt_path = BASE / "validation" / token / "run/supervised_retest_receipt.json"
        audit = json.loads(audit_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        if receipt["candidate_id"] != candidate or receipt["holdout_accessed"]:
            raise ValueError("retest lineage mismatch")
        stress = audit["results"]["stress"]
        checks = {
            "minimum_trades_15": stress["trades"] >= 15,
            "minimum_stress_profit_factor_1_15": (stress["profit_factor"] or 0) >= 1.15,
            "minimum_positive_quarters_5": stress["positive_quarters"] >= 5,
            "maximum_drawdown_25pct": stress["maximum_drawdown_pct_close_to_close"] <= 25,
        }
        rows.append({
            "candidate_id": candidate,
            "decision": "PASS_VALIDATION" if all(checks.values()) else "REJECT_VALIDATION",
            "checks": checks, "stress_1000": stress,
            "audit_path": str(audit_path.relative_to(ROOT)), "audit_sha256": sha(audit_path),
            "receipt_path": str(receipt_path.relative_to(ROOT)),
            "receipt_sha256": sha(receipt_path),
        })
    survivors = [row["candidate_id"] for row in rows if row["decision"] == "PASS_VALIDATION"]
    result = {
        "schema_version": 1,
        "decision": "PASS_EEM_D1_VALIDATION_SURVIVORS" if survivors
                    else "REJECT_EEM_D1_NO_VALIDATION_SURVIVOR",
        "family_freeze_sha256": sha(freeze_path), "survivors": survivors,
        "candidates": rows, "oos_2024_accessed": False,
        "optimization_performed": False, "paper_authorized": False,
        "live_authorized": False,
    }
    (BASE / "validation_adjudication_v1.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(adjudicate(), indent=2))
