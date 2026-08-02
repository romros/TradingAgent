#!/usr/bin/env python3
"""Comprova una campanya abans de generar; no executa StrategyQuant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "id", "question", "family", "symbols", "timeframe", "direction", "engine",
    "sq_version", "capital", "periods", "costs", "minimum_trades",
    "maximum_drawdown_pct", "attempt_budget", "discard_criteria",
    "prior_failure_ids", "frozen",
}
PERIODS = {"development", "validation", "holdout"}
COSTS = {"spread", "commission", "slippage"}


def unresolved(value: object) -> bool:
    return isinstance(value, str) and value.startswith("TO_")


def assess(plan: dict, failure_memory: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(f"missing:{field}" for field in sorted(REQUIRED - plan.keys()))
    if blockers:
        return {"ready": False, "blockers": blockers, "warnings": warnings}

    if plan["frozen"] is not True:
        blockers.append("protocol_not_frozen")
    for field in sorted(PERIODS - plan["periods"].keys()):
        blockers.append(f"missing_period:{field}")
    for field, value in plan["periods"].items():
        if unresolved(value):
            blockers.append(f"unresolved_period:{field}")
    if len(set(plan["periods"].values())) != len(plan["periods"]):
        blockers.append("periods_not_distinct")
    for field in sorted(COSTS - plan["costs"].keys()):
        blockers.append(f"missing_cost:{field}")
    for field, value in plan["costs"].items():
        if unresolved(value):
            blockers.append(f"unresolved_cost:{field}")
    if not plan["discard_criteria"]:
        blockers.append("discard_criteria_empty")
    if plan["attempt_budget"] < 1:
        blockers.append("invalid_attempt_budget")

    known = {entry["id"]: entry for entry in failure_memory.get("entries", [])}
    referenced = plan["prior_failure_ids"]
    unknown = sorted(set(referenced) - known.keys())
    blockers.extend(f"unknown_prior_failure:{item}" for item in unknown)
    related = [entry for entry in known.values() if entry["family"] == plan["family"]]
    missing_related = [entry["id"] for entry in related if entry["id"] not in referenced]
    blockers.extend(f"unacknowledged_prior_failure:{item}" for item in missing_related)
    if referenced and not plan.get("difference_from_prior", "").strip():
        blockers.append("difference_from_prior_missing")
    if not referenced:
        warnings.append("no_prior_failures_linked")

    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "decision": "GENERATE_CHEAP_STAGE" if not blockers else "DO_NOT_START",
        "note": "Un preflight positiu autoritza només la generació barata, no el holdout ni trading.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--failure-memory", type=Path,
        default=Path(__file__).resolve().parents[1] / "experiments/failure-memory.json",
    )
    args = parser.parse_args()
    result = assess(
        json.loads(args.plan.read_text(encoding="utf-8")),
        json.loads(args.failure_memory.read_text(encoding="utf-8")),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
