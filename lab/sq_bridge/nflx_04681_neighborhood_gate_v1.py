#!/usr/bin/env python3
"""Evaluate the preregistered NFLX 0.4681 one-axis neighborhood."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.ibkr_equity_small_account_audit_v2 import audit


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(spec_path: Path, manifest_path: Path, retest_root: Path) -> dict:
    spec = json.loads(spec_path.read_text())
    materialization = json.loads(manifest_path.read_text())
    gate = spec["gate"]
    capital = gate["capital_usd"]
    expected = {row["candidate_id"]: row for row in materialization["neighbors"]}
    if len(expected) != len(spec["neighbors"]):
        raise ValueError("materialized neighborhood does not match preregistration")

    rows = []
    for candidate_id, materialized in sorted(expected.items()):
        receipt_path = retest_root / candidate_id / "run" / "supervised_retest_receipt.json"
        receipt = json.loads(receipt_path.read_text())
        orders_path = Path(receipt["orders_csv_path"])
        if (receipt["decision"] != "PASS_SUPERVISED_RETEST"
                or receipt["candidate_id"] != candidate_id
                or receipt["candidate_input_sqx_sha256"] != materialized["sqx_sha256"]
                or receipt["holdout_accessed"] is not False
                or sha(orders_path) != receipt["orders_csv_sha256"]):
            raise ValueError(f"invalid retest lineage: {candidate_id}")
        try:
            evidence = audit(
                candidate_id=candidate_id,
                orders_path=orders_path,
                capital_scenarios=[capital],
                allow_same_bar_d1=True,
                exclude_end_test=True,
                stage="validation",
            )
            stress = evidence["results"][str(capital)]["stress"]
            error = None
        except ValueError as exc:
            evidence, stress, error = None, None, str(exc)
        rows.append({
            "candidate_id": candidate_id,
            "parameters": materialized["parameters"],
            "receipt_path": str(receipt_path),
            "receipt_sha256": sha(receipt_path),
            "audit": evidence,
            "stress": stress,
            "execution_parity_error": error,
        })

    usable = [row for row in rows if row["stress"] is not None]
    profitable = [row for row in usable if row["stress"]["return_pct"] > 0]
    pf_rows = [row for row in usable
               if (row["stress"]["profit_factor"] or 0) >= 1.10]
    maximum_dd = max((row["stress"]["maximum_drawdown_pct_close_to_close"]
                      for row in usable), default=None)
    checks = {
        "minimum_profitable_neighbors_ratio_stress":
            len(profitable) / len(rows)
            >= gate["minimum_profitable_neighbors_ratio_stress"],
        "minimum_neighbors_with_profit_factor_gte_1_10":
            len(pf_rows) >= gate["minimum_neighbors_with_profit_factor_gte_1_10"],
        "maximum_neighbor_close_to_close_drawdown_pct":
            maximum_dd is not None
            and maximum_dd <= gate["maximum_neighbor_close_to_close_drawdown_pct"],
        "all_neighbors_have_executable_parity": len(usable) == len(rows),
    }
    passed = all(checks.values())
    return {
        "schema_version": 1,
        "stage": "NFLX_04681_PREREGISTERED_PARAMETER_NEIGHBORHOOD_2017_2024",
        "decision": "PASS_PARAMETER_NEIGHBORHOOD" if passed
                    else "REJECT_PARAMETER_NEIGHBORHOOD",
        "spec_path": str(spec_path),
        "spec_sha256": sha(spec_path),
        "materialization_manifest_path": str(manifest_path),
        "materialization_manifest_sha256": sha(manifest_path),
        "capital_usd": capital,
        "evaluated": len(rows),
        "usable": len(usable),
        "profitable": len(profitable),
        "profitable_ratio": len(profitable) / len(rows),
        "profit_factor_gte_1_10": len(pf_rows),
        "maximum_drawdown_pct_close_to_close": maximum_dd,
        "checks": checks,
        "results": rows,
        "selection_or_optimization_after_results": False,
        "holdout_2025_accessed": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--retest-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.spec, args.manifest, args.retest_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "decision", "evaluated", "usable", "profitable", "profitable_ratio",
        "profit_factor_gte_1_10", "maximum_drawdown_pct_close_to_close", "checks")},
        indent=2))


if __name__ == "__main__":
    main()
