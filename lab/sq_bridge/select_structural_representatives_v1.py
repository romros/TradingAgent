#!/usr/bin/env python3
"""Freeze train-only representatives without selecting the prettiest backtest."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path


def select(inventory: dict, limit: int = 8) -> dict:
    rows = {row["strategy"]: row for row in inventory["candidates"]}
    eligible = [family for family in inventory["families"] if family["count"] >= 2]
    chosen = []
    for family in eligible:
        members = [rows[name] for name in family["members"]]
        medians = {key: statistics.median(row[key] for row in members)
                   for key in ("trades", "profit_drawdown_ratio", "complexity")}
        def distance(row: dict) -> tuple:
            normalized = sum(abs(row[key] - medians[key]) / max(abs(medians[key]), 1)
                             for key in medians)
            return (normalized, row["strategy"])
        representative = min(members, key=distance)
        chosen.append({
            "structural_family_sha256": family["structural_family_sha256"],
            "family_support": family["count"],
            "candidate_id": representative["strategy"],
            "candidate_sqx_sha256": representative["sqx_sha256"],
            "selection_distance_to_family_median": distance(representative)[0],
        })
    chosen.sort(key=lambda row: (-row["family_support"], row["structural_family_sha256"]))
    chosen = chosen[:limit]
    return {
        "schema_version": 1,
        "stage": "train_structural_selection",
        "selection_rule": "families_with_at_least_2_members_then_medoid_of_trades_profit_dd_complexity",
        "selection_uses_validation": False,
        "selection_uses_oos": False,
        "source_inventory_sha256": inventory["source_inventory_sha256"],
        "eligible_family_count": len(eligible),
        "representative_limit": limit,
        "representatives": chosen,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if args.limit < 1:
        raise ValueError("limit must be positive")
    raw = args.inventory.read_bytes()
    inventory = json.loads(raw)
    result = select(inventory, args.limit)
    if result["source_inventory_sha256"] != inventory["source_inventory_sha256"]:
        raise ValueError("inventory lineage mismatch")
    result["inventory_file_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
