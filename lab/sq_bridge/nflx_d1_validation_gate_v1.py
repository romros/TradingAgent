#!/usr/bin/env python3
"""Apply the frozen NFLX validation gate without accessing sealed 2024 OOS."""
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
    representatives = selection.get("representatives", selection.get("selected", []))
    for representative in representatives:
        candidate = representative.get("candidate_id", representative.get("strategy"))
        if not candidate:
            raise ValueError("selection representative has no candidate identifier")
        token = candidate.replace("Strategy ", "").replace(".", "_")
        receipt_path = validation_root / token / "run" / "supervised_retest_receipt.json"
        receipt = json.loads(receipt_path.read_text())
        orders = Path(receipt["orders_csv_path"])
        if (receipt["decision"] != "PASS_SUPERVISED_RETEST"
                or receipt["candidate_id"] != candidate
                or receipt["holdout_accessed"] is not False
                or sha(orders) != receipt["orders_csv_sha256"]):
            raise ValueError(f"invalid validation lineage: {candidate}")
        try:
            evidence = audit(
                candidate_id=candidate,
                orders_path=orders,
                capital_scenarios=gate["capital_scenarios_usd"],
                allow_same_bar_d1=True,
                stage="validation",
            )
        except ValueError as exc:
            rows.append({
                "candidate_id": candidate,
                "token": token,
                "receipt_path": str(receipt_path),
                "receipt_sha256": sha(receipt_path),
                "audit": None,
                "execution_parity_error": str(exc),
                "checks_by_capital": {},
                "passing_capitals_usd": [],
                "passed": False,
            })
            continue
        stress_by_capital = {
            str(capital): evidence["results"][str(capital)]["stress"]
            for capital in gate["capital_scenarios_usd"]
        }
        checks_by_capital = {}
        for capital, stress in stress_by_capital.items():
            checks_by_capital[capital] = {
                "minimum_trades": stress["trades"] >= gate["minimum_trades"],
                "minimum_stress_profit_factor": (stress["profit_factor"] or 0)
                    >= gate["minimum_stress_profit_factor"],
                "minimum_positive_half_years": stress["positive_half_years"]
                    >= gate["minimum_positive_half_years"],
                "maximum_drawdown": stress["maximum_drawdown_pct_close_to_close"]
                    <= gate["maximum_drawdown_pct"],
            }
        passing_capitals = [capital for capital, checks in checks_by_capital.items()
                            if all(checks.values())]
        rows.append({
            "candidate_id": candidate,
            "token": token,
            "receipt_path": str(receipt_path),
            "receipt_sha256": sha(receipt_path),
            "audit": evidence,
            "checks_by_capital": checks_by_capital,
            "passing_capitals_usd": [int(value) for value in passing_capitals],
            "passed": bool(passing_capitals),
        })
    survivors = [row["candidate_id"] for row in rows if row["passed"]]
    return {
        "schema_version": 1,
        "stage": "NFLX_D1_2022_2023_VALIDATION",
        "decision": "PASS_VALIDATION_SURVIVORS" if survivors
                    else "REJECT_NFLX_D1_VOLATILITY_BREAKOUT_FAMILY",
        "spec_sha256": sha(spec_path),
        "selection_sha256": sha(selection_path),
        "validation_gate": gate,
        "evaluated": len(rows),
        "survivors": survivors,
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
    print(json.dumps({
        "decision": result["decision"],
        "survivors": result["survivors"],
        "diagnostics": [{
            "candidate": row["candidate_id"],
            "passing_capitals_usd": row["passing_capitals_usd"],
            "execution_parity_error": row.get("execution_parity_error"),
            "stress": {capital: {
                "trades": metrics["trades"],
                "return_pct": metrics["return_pct"],
                "profit_factor": metrics["profit_factor"],
                "positive_half_years": metrics["positive_half_years"],
                "maximum_drawdown_pct": metrics["maximum_drawdown_pct_close_to_close"],
            } for capital, metrics in {
                key: row["audit"]["results"][key]["stress"]
                for key in row["audit"]["results"]
            }.items()},
        } if row["audit"] is not None else {
            "candidate": row["candidate_id"],
            "execution_parity_error": row["execution_parity_error"],
            "passing_capitals_usd": [],
            "stress": {},
        } for row in result["results"]],
    }, indent=2))


if __name__ == "__main__":
    main()
