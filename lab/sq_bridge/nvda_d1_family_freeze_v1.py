#!/usr/bin/env python3
"""Freeze one simple, translatable NVDA representative per chosen family."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from lab.sq_bridge.sqx_extract import extract


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/ibkr_sq_v2/nvda_d1_simple_discovery_v1"
INVENTORY = BASE / "train_inventory.json"
SOURCE = BASE / "train_candidates"
DESTINATION = BASE / "frozen_family_representatives"

# Frozen before validation performance.  The representatives cover distinct,
# interpretable entry archetypes; selection uses train complexity/P-DD only.
SELECTION = {
    "adx_regime": "Strategy 0.11",
    "close_pullback": "Strategy 0.142",
    "ema_rising": "Strategy 0.157",
    "ma_relative": "Strategy 0.168",
    "roc_turn": "Strategy 0.229",
    "rsi_relative": "Strategy 0.123",
    "sma_regime": "Strategy 0.119",
    "price_above_sma": "Strategy 0.56",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze() -> dict:
    inventory = json.loads(INVENTORY.read_text())
    by_name = {row["strategy"]: row for row in inventory["candidates"]}
    if set(SELECTION.values()) - set(by_name):
        raise ValueError("frozen representative absent from inventory")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    if list(DESTINATION.glob("*.sqx")):
        raise ValueError("destination must be empty before first freeze")
    rows = []
    for family, candidate in sorted(SELECTION.items()):
        source = SOURCE / by_name[candidate]["file"]
        contract = extract(source)
        if contract["translation_status"] != "SUPPORTED_SUBSET":
            raise ValueError(f"{candidate} is not in the supported subset")
        target = DESTINATION / source.name
        shutil.copy2(source, target)
        if sha256(target) != by_name[candidate]["sqx_sha256"]:
            raise ValueError(f"copy hash mismatch: {candidate}")
        rows.append({
            "family": family,
            "candidate": candidate,
            "sqx_path": str(target.relative_to(ROOT)),
            "sqx_sha256": sha256(target),
            "train_trades": by_name[candidate]["trades"],
            "train_profit_drawdown_ratio": by_name[candidate]["profit_drawdown_ratio"],
            "complexity": by_name[candidate]["complexity"],
            "entry_indicator_types": by_name[candidate]["entry_indicator_types"],
            "translation_status": contract["translation_status"],
        })
    result = {
        "schema_version": 1,
        "decision": "PASS_FAMILIES_FROZEN_BEFORE_VALIDATION",
        "selection_policy": (
            "one simple interpretable representative for each distinct chosen "
            "entry archetype; train complexity and profit/drawdown only"
        ),
        "inventory_sha256": sha256(INVENTORY),
        "representative_count": len(rows),
        "validation_accessed_before_freeze": False,
        "oos_2024_accessed": False,
        "representatives": rows,
    }
    lock = BASE / "family_freeze_v1.json"
    lock.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(freeze(), indent=2))
