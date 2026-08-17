#!/usr/bin/env python3
"""Compile an unstarted KO resource project for the frozen PEP/KO transfer."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1"
SPEC = ROOT / "lab/sq_bridge/pep_ko_d1_trend_pullback_v1.json"
LOCK = ROOT / "lab/sq_bridge/pep_ko_d1_trend_pullback_v1.lock.json"
SOURCE = ROOT / "data/ibkr_sq_v2/preflight/KOUSUSD_CANONICAL_D1_2017_2024.csv"
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    spec, lock = (json.loads(path.read_text()) for path in (SPEC, LOCK))
    if sha(SOURCE) != lock["ko_source_sha256"] or spec["performance_accessed_for_this_family"]:
        raise ValueError("frozen KO source contract failed")
    target = BASE / "ko_resource"
    target.mkdir(parents=True, exist_ok=True)
    (target / "KOUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv").write_bytes(SOURCE.read_bytes())
    registry = json.loads((BASE / "frozen_market_registry.json").read_text())
    market = registry["markets"].pop("PEP")
    market["sq_symbol"] = spec["mandatory_transfer_asset"]["sq_symbol"]
    resource = market["sq_resource_attributes"]
    resource["uSymbol"] = resource["uSymbolName"] = "KO_IBKR_TREND_PULLBACK_V1"
    instrument = market["sq_instrument_attributes"]
    instrument.update({"instrument": "KO_IBKR_TREND_PULLBACK_V1",
                       "description": "KO D1 trend pullback transfer",
                       "exchange": "NYSE"})
    registry["markets"]["KO"] = market
    registry_path = target / "frozen_market_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    periods = spec["periods"]
    split = {"train_from": periods["train_from"], "train_to": periods["train_to"],
             "validation_from": periods["validation_from"],
             "validation_to": periods["validation_to"],
             "oos_from": periods["sealed_oos_from"], "oos_to": periods["sealed_oos_to"],
             "holdout_from": "2025-01-02", "holdout_to": "2025-12-31"}
    project = target / "project.cfx"
    manifest = build(
        SCAFFOLD, project, "IBKR_KO_D1_TREND_PULLBACK_RESOURCE_V1", "KO",
        registry_path, BASE / "frozen_methodology.json",
        date.fromisoformat(periods["train_from"]), date(2025, 12, 31), 1,
        spec["discovery"]["search_profile"], "random-generation", 1, 0, None,
        "long", periods_override=split)
    receipt = {"decision": "PASS_KO_TRANSFER_RESOURCE_READY",
               "project_sha256": manifest["output_sha256"],
               "source_sha256": sha(SOURCE), "performance_accessed": False,
               "sqcli_started": False, "holdout_2025_accessed": False,
               "paper_authorized": False, "live_authorized": False}
    (target / "compile_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
