#!/usr/bin/env python3
"""Apply the frozen GOOG validation gate to uncensored SQ order exports."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.ibkr_equity_small_account_audit_v2 import audit


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(spec_path: Path, selection_path: Path, validation_root: Path) -> dict:
    spec = json.loads(spec_path.read_text())
    selection = json.loads(selection_path.read_text())
    gate = spec["validation_gate"]
    rows = []
    for representative in selection["representatives"]:
        candidate = representative["candidate_id"]
        token = candidate.replace("Strategy ", "").replace(".", "_")
        receipt_path = validation_root / token / "run" / "supervised_retest_receipt.json"
        receipt = json.loads(receipt_path.read_text())
        orders = Path(receipt["orders_csv_path"])
        if (receipt["decision"] != "PASS_SUPERVISED_RETEST"
                or receipt["candidate_id"] != candidate
                or receipt["holdout_accessed"] is not False
                or sha(orders) != receipt["orders_csv_sha256"]):
            raise ValueError(f"invalid validation lineage: {candidate}")
        evidence = audit(candidate_id=candidate, orders_path=orders,
                         capital_scenarios=[gate["capital_usd"]],
                         allow_same_bar_d1=True, stage="validation")
        stress = evidence["results"][str(gate["capital_usd"])]["stress"]
        checks = {
            "minimum_trades": stress["trades"] >= gate["minimum_trades"],
            "minimum_stress_profit_factor": (stress["profit_factor"] or 0)
                >= gate["minimum_stress_profit_factor"],
            "minimum_positive_quarters": stress["positive_quarters"]
                >= gate["minimum_positive_quarters"],
            "maximum_drawdown": stress["maximum_drawdown_pct_close_to_close"]
                <= gate["maximum_close_to_close_drawdown_pct"],
        }
        rows.append({"candidate_id": candidate, "token": token,
                     "family_support": representative["family_support"],
                     "receipt_path": str(receipt_path),
                     "receipt_sha256": sha(receipt_path),
                     "audit": evidence, "checks": checks,
                     "passed": all(checks.values())})
    return {
        "schema_version": 1,
        "stage": f"{spec['asset']}_D1_2022_2023_VALIDATION",
        "decision": "PASS_VALIDATION_SURVIVORS" if any(r["passed"] for r in rows)
                    else f"REJECT_{spec['asset']}_PRICE_ACTION_FAMILY",
        "spec_sha256": sha(spec_path),
        "selection_sha256": sha(selection_path),
        "validation_gate": gate,
        "evaluated": len(rows),
        "survivors": [r["candidate_id"] for r in rows if r["passed"]],
        "results": rows,
        "oos_2024_accessed": False,
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--validation-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.spec, args.selection, args.validation_root)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "evaluated": result["evaluated"],
                      "survivors": result["survivors"],
                      "diagnostics": [{"candidate": r["candidate_id"],
                                       "stress": r["audit"]["results"]["1000"]["stress"],
                                       "checks": r["checks"]}
                                      for r in result["results"]]}, indent=2))


if __name__ == "__main__":
    main()
