#!/usr/bin/env python3
"""Freeze train-only EEM representatives before temporal validation."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/ibkr_sq_v2/eem_d1_simple_discovery_v1"
SELECTION = BASE / "train_structural_selection_eligible.json"
INVENTORY = BASE / "train_inventory.json"
SOURCE = BASE / "train_candidates"
DESTINATION = BASE / "frozen_family_representatives"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze() -> dict:
    selection = json.loads(SELECTION.read_text())
    inventory = json.loads(INVENTORY.read_text())
    by_name = {row["strategy"]: row for row in inventory["candidates"]}
    if selection["selection_uses_validation"] or selection["selection_uses_oos"]:
        raise ValueError("selection leaked future performance")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    if list(DESTINATION.glob("*.sqx")):
        raise ValueError("freeze destination must start empty")
    frozen = []
    for representative in selection["representatives"]:
        name = representative["candidate_id"]
        source = SOURCE / by_name[name]["file"]
        if sha(source) != representative["candidate_sqx_sha256"]:
            raise ValueError(f"candidate hash mismatch: {name}")
        target = DESTINATION / source.name
        shutil.copy2(source, target)
        frozen.append({**representative, "sqx_path": str(target.relative_to(ROOT)),
                       "sqx_sha256": sha(target)})
    result = {
        "schema_version": 1,
        "decision": "PASS_EEM_FAMILIES_FROZEN_BEFORE_VALIDATION",
        "selection_policy": selection["selection_rule"],
        "selection_sha256": sha(SELECTION),
        "inventory_sha256": sha(INVENTORY),
        "representative_count": len(frozen),
        "validation_accessed_before_freeze": False,
        "oos_2024_accessed": False,
        "representatives": frozen,
        "paper_authorized": False,
        "live_authorized": False
    }
    (BASE / "family_freeze_v1.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(freeze(), indent=2))
