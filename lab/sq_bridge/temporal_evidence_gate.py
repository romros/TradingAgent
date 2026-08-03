#!/usr/bin/env python3
"""Global performance-period gate for Alquimia research proposals."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


CLAIMS = {"internal_walk_forward", "independent_validation", "global_holdout", "parity_only"}


def day(value: str) -> date:
    return date.fromisoformat(value)


def overlaps(left_from: str, left_to: str, right_from: str, right_to: str) -> bool:
    return max(day(left_from), day(right_from)) <= min(day(left_to), day(right_to))


def contains(outer: dict, start: str, end: str) -> bool:
    return day(outer["from"]) <= day(start) <= day(end) <= day(outer["to"])


def verify_ledger(ledger: dict, root: Path) -> None:
    for relative, expected in ledger["artifact_sha256"].items():
        path = root / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"LEDGER_ARTIFACT_MISMATCH:{relative}")
    holdout = ledger["global_holdout"]
    if holdout["accessed_for_performance"] and not holdout["release_authorized"]:
        raise ValueError("UNAUTHORIZED_GLOBAL_HOLDOUT_ACCESS_RECORDED")


def evaluate(ledger: dict, proposal: dict) -> dict:
    claim = proposal.get("claim")
    if claim not in CLAIMS: raise ValueError(f"UNKNOWN_CLAIM:{claim}")
    assets = proposal.get("assets", [])
    if not assets or any(asset not in ledger["reusable_research_pool"] for asset in assets):
        raise ValueError("UNKNOWN_OR_EMPTY_ASSET_SET")
    start, end = proposal["from"], proposal["to"]
    if day(start) > day(end): raise ValueError("INVALID_PERIOD")
    holdout = ledger["global_holdout"]
    result = {"schema_version": 1, "family_id": proposal["family_id"], "claim": claim,
              "assets": assets, "from": start, "to": end, "independent": False,
              "performance_promotion_authorized": False, "reasons": []}
    if claim == "parity_only":
        if proposal.get("performance_metrics_accessed", False):
            result.update(decision="BLOCK_PARITY_SCOPE_VIOLATION"); result["reasons"].append("Parity-only work cannot inspect signals or performance.")
        else:
            result.update(decision="PASS_DATA_QUALITY_ONLY"); result["reasons"].append("Price/coverage inspection does not consume performance holdout.")
        return result
    if claim == "internal_walk_forward":
        outside = [asset for asset in assets if not contains(ledger["reusable_research_pool"][asset], start, end)]
        if outside:
            result.update(decision="BLOCK_OUTSIDE_REUSABLE_POOL"); result["reasons"].append(f"Outside reusable pool for: {','.join(outside)}")
        else:
            result.update(decision="PASS_INTERNAL_NON_INDEPENDENT"); result["reasons"].append("Allowed for development/internal walk-forward; cannot support an independent OOS claim.")
        return result
    if claim == "global_holdout":
        exact = start == holdout["from"] and end == holdout["to"] and set(assets).issubset(holdout["assets"])
        cohort_ok = proposal.get("cohort_id") == holdout["authorized_cohort_id"]
        if exact and holdout["release_authorized"] and cohort_ok and not holdout["accessed_for_performance"]:
            result.update(decision="PASS_ONE_TIME_GLOBAL_HOLDOUT", independent=True, performance_promotion_authorized=True)
        else:
            result.update(decision="BLOCK_GLOBAL_HOLDOUT_RELEASE_REQUIRED"); result["reasons"].append("A one-time preregistered cohort release is not authorized.")
        return result
    if overlaps(start, end, holdout["from"], holdout["to"]):
        result.update(decision="BLOCK_GLOBAL_HOLDOUT_RELEASE_REQUIRED"); result["reasons"].append("Proposed independent validation overlaps the sealed global holdout.")
        return result
    collisions = []
    for event in ledger["events"]:
        if event["performance_accessed"] and set(assets) & set(event["assets"]) and overlaps(start, end, event["from"], event["to"]):
            collisions.append({key: event[key] for key in ("family_id", "stage", "from", "to")})
    if collisions:
        result.update(decision="BLOCK_REUSED_PERFORMANCE_PERIOD", collisions=collisions)
        result["reasons"].append("At least one asset-period has already been inspected for strategy performance.")
    else:
        result.update(decision="PASS_INDEPENDENT_VALIDATION", independent=True)
        result["reasons"].append("No recorded performance-period collision.")
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--ledger", type=Path, required=True); parser.add_argument("--proposal", type=Path, required=True); parser.add_argument("--root", type=Path, default=Path(".")); parser.add_argument("--output", type=Path); args = parser.parse_args()
    ledger, proposal = json.loads(args.ledger.read_text()), json.loads(args.proposal.read_text()); verify_ledger(ledger, args.root); result = evaluate(ledger, proposal)
    if args.output: args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
