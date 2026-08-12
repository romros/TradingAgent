#!/usr/bin/env python3
"""Fail closed if the clean-slate IBKR/SQ universe violates its contract."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "lab/sq_bridge/ibkr_new_universe_v2.json"


def validate(registry_path: Path = REGISTRY) -> dict[str, object]:
    doc = json.loads(registry_path.read_text(encoding="utf-8"))
    catalog_meta = doc["data_catalog"]
    catalog_path = Path(catalog_meta["local_catalog_path"])
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    if digest != catalog_meta["catalog_sha256"]:
        raise ValueError("Dukascopy catalog hash changed; recertify before use")

    catalog: dict[str, list[str]] = {}
    # SQ ships this vendor catalog as Windows-1252 (for example it contains ®).
    # Do not use permissive replacement: a changed encoding must remain visible.
    with catalog_path.open(encoding="cp1252", newline="") as handle:
        for row in csv.reader(handle, delimiter=";"):
            if row:
                catalog[row[0].upper()] = row

    excluded = {s.upper() for s in doc["hard_exclusions"]["known_symbols"]}
    reauthorized = {s.upper() for s in doc.get("explicit_reauthorizations", {}).get("symbols", [])}
    seen: set[str] = set()
    asset_classes: set[str] = set()
    for asset in doc["candidates"]:
        symbol = asset["symbol"].upper()
        if symbol in seen:
            raise ValueError(f"duplicate symbol: {symbol}")
        if symbol in excluded and symbol not in reauthorized:
            raise ValueError(f"old/Ostium symbol leaked into new universe: {symbol}")
        if "crypto" in asset["asset_class"].lower():
            raise ValueError(f"crypto is forbidden: {symbol}")
        if asset["new_vs_ostium"] is not True and not asset.get("reauthorized_clean_slate"):
            raise ValueError(f"new_vs_ostium must be true: {symbol}")
        sq_symbol = asset["sq_data_symbol"].upper()
        if sq_symbol not in catalog:
            raise ValueError(f"missing from frozen Dukascopy catalog: {sq_symbol}")
        seen.add(symbol)
        asset_classes.add(asset["asset_class"])

    if not any(a["priority"] == 1 for a in doc["candidates"]):
        raise ValueError("at least one priority-1 asset is required")

    return {
        "status": "PASS",
        "registry": str(registry_path.relative_to(ROOT)),
        "candidate_count": len(seen),
        "explicitly_reauthorized_count": len(reauthorized),
        "priority_1_count": sum(a["priority"] == 1 for a in doc["candidates"]),
        "asset_classes": sorted(asset_classes),
        "catalog_sha256": digest,
        "next_gate": doc["next_gate"]["name"]
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
