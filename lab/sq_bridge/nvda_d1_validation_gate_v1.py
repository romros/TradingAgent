#!/usr/bin/env python3
"""Adjudicate frozen NVDA families without opening the 2024 OOS."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/ibkr_sq_v2/nvda_d1_simple_discovery_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def adjudicate() -> dict:
    lock_path = BASE / "family_freeze_v1.json"
    lock = json.loads(lock_path.read_text())
    rows = []
    for frozen in lock["representatives"]:
        candidate = frozen["candidate"]
        slug = candidate.removeprefix("Strategy ").replace(".", "_")
        audit_path = BASE / "validation" / slug / "ibkr_cost_audit.json"
        receipt_path = BASE / "validation" / slug / "run/supervised_retest_receipt.json"
        audit = json.loads(audit_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        stress = audit["results"]["1000"]["stress"]
        checks = {
            "minimum_trades_15": stress["trades"] >= 15,
            "minimum_stress_profit_factor_1_15": (
                stress["profit_factor"] is not None and stress["profit_factor"] >= 1.15
            ),
            "minimum_positive_quarters_5": stress["positive_quarters"] >= 5,
            "maximum_close_drawdown_25pct": (
                stress["maximum_drawdown_pct_close_to_close"] <= 25
            ),
        }
        rows.append({
            "candidate": candidate,
            "family": frozen["family"],
            "decision": "PASS_VALIDATION" if all(checks.values()) else "REJECT_VALIDATION",
            "checks": checks,
            "stress_1000": stress,
            "audit_path": str(audit_path.relative_to(ROOT)),
            "audit_sha256": sha256(audit_path),
            "native_retest_receipt_path": str(receipt_path.relative_to(ROOT)),
            "native_retest_receipt_sha256": sha256(receipt_path),
        })
    survivors = [row["candidate"] for row in rows if row["decision"] == "PASS_VALIDATION"]
    result = {
        "schema_version": 1,
        "decision": "REJECT_NVDA_D1_DISCOVERY_NO_VALIDATION_SURVIVOR" if not survivors
                    else "PASS_NVDA_D1_VALIDATION_SURVIVORS",
        "family_freeze_path": str(lock_path.relative_to(ROOT)),
        "family_freeze_sha256": sha256(lock_path),
        "cost_scenario": "1000_usd_stress_whole_shares_no_leverage",
        "survivors": survivors,
        "candidates": rows,
        "oos_2024_accessed": False,
        "optimization_performed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }
    output = BASE / "validation_adjudication_v1.json"
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return result


if __name__ == "__main__":
    value = adjudicate()
    print(json.dumps({"decision": value["decision"], "survivors": value["survivors"]}, indent=2))
