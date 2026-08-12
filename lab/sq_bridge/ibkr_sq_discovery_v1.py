#!/usr/bin/env python3
"""Build the sealed first SQCLI discovery batch for IBUS500 M15."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build
from lab.sq_bridge.sq_project_contract import verify_genetic_project


ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_batch(output_dir: Path) -> dict:
    prereg = ROOT / "lab/sq_bridge/ibkr_aggressive_preregistration_v1.json"
    spec = json.loads(prereg.read_text())
    if (spec["research_pipeline"]["primary_discovery_engine"] != "StrategyQuant SQCLI"
            or spec["venue"]["instrument"] != "IBUS500"
            or spec["temporal_contract"]["prospective_holdout_accessed"] is not False):
        raise ValueError("IBKR preregistration does not authorize discovery")
    scaffold = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")
    registry = ROOT / "lab/sq_bridge/ibkr_sq_markets_v1.json"
    methodology = ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    projects = {}
    for side in ("long", "short", "both"):
        hypothesis = f"ibus500_m15_generic_{side}_v9"
        project_name = f"IBKR_IBUS500_M15_{side.upper()}_V9"
        cfx = output_dir / hypothesis / "project.cfx"
        manifest = build(
            scaffold, cfx, project_name, "IBUS500", registry, methodology,
            date(2012, 1, 19), date(2025, 12, 31), 20,
            "generic_translatable", "genetic-evolution", 10000, 120, None, side)
        shape = verify_genetic_project(cfx, manifest)
        projects[hypothesis] = {
            "project_name": project_name,
            "project_cfx_path": str(cfx.resolve()),
            "project_cfx_sha256": sha(cfx),
            "project_manifest_path": str(cfx.with_suffix(".manifest.json").resolve()),
            "project_manifest_sha256": sha(cfx.with_suffix(".manifest.json")),
            "sq_genetic_shape": shape,
        }
    result = {
        "schema_version": 1,
        "decision": "PASS_CFX_BATCH_READY",
        "campaign_id": spec["campaign_id"],
        "preregistration_path": str(prereg.resolve()),
        "preregistration_sha256": sha(prereg),
        "projects": projects,
        "selected_hypothesis_ids": sorted(projects),
        "sqcli_started": False,
        "paper_authorized": False,
        "live_authorized": False
    }
    path = output_dir / "project_batch.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    result = compile_batch(ROOT / "data/ibkr_sq_v1/projects")
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"])}, indent=2))
