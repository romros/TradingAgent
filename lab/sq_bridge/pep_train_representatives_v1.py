#!/usr/bin/env python3
"""Freeze up to five structurally distinct PEP representatives using train only."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def select(inventory: dict) -> dict:
    pareto = set(inventory["pareto_candidates"])
    eligible = [row for row in inventory["candidates"]
                if row["strategy"] in pareto and row["trades"] >= 30
                and row["profit"] > 0 and row["drawdown"] > 0]
    eligible.sort(key=lambda row: (-row["profit_drawdown_ratio"], -row["fitness"],
                                   -row["profit"], row["complexity"], row["strategy"]))
    chosen, families, entries = [], set(), set()
    for row in eligible:
        if (row["structural_family_sha256"] in families
                or row["entry_indicator_archetype_sha256"] in entries):
            continue
        chosen.append({key: row[key] for key in (
            "strategy", "file", "sqx_sha256", "structural_family_sha256",
            "entry_indicator_archetype_sha256", "trades", "profit", "drawdown",
            "profit_drawdown_ratio", "fitness", "complexity",
            "entry_indicator_types")})
        families.add(row["structural_family_sha256"])
        entries.add(row["entry_indicator_archetype_sha256"])
        if len(chosen) == 5:
            break
    return {
        "schema_version": 1,
        "decision": "PASS_FREEZE_PEP_TRAIN_REPRESENTATIVES" if chosen
                    else "REJECT_NO_PEP_TRAIN_REPRESENTATIVE",
        "selection_rule": "Pareto only; >=30 trades; positive profit; rank profit/DD, fitness, profit, complexity, name; unique structural and entry-indicator archetypes",
        "inventory_sha256": inventory["source_inventory_sha256"],
        "selected_count": len(chosen), "selected": chosen,
        "validation_accessed": False, "transfer_ko_accessed": False,
        "oos_accessed": False, "holdout_2025_accessed": False,
        "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selected-dir", required=True, type=Path)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    result = select(inventory)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    args.selected_dir.mkdir(parents=True, exist_ok=True)
    for row in result["selected"]:
        source = Path(row["file"])
        if not source.is_absolute():
            source = Path(inventory["source"]) / source
        shutil.copy2(source, args.selected_dir / source.name)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
