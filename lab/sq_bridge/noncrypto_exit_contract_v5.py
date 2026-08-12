#!/usr/bin/env python3
"""Fail-closed verifier for the preperformance Alquimia v5 exit semantics."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "lab/sq_bridge/noncrypto_exit_contract_v5.json"
PREREG = ROOT / "lab/sq_bridge/noncrypto_campaign_preregistration_v5.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError("JSON object required")
    return value


def verify(contract_path: Path = CONTRACT, prereg_path: Path = PREREG) -> dict[str, Any]:
    contract, prereg = _load(contract_path), _load(prereg_path)
    if contract.get("performance_accessed") is not False or contract.get("holdout_accessed") is not False:
        raise ValueError("exit contract must remain performance blind")
    common = contract["common"]
    if (common["entry"], common["stop_may_widen"], common["intrabar_collision"]) != (
            "NEXT_BAR_OPEN", False, "STOP_FIRST"):
        raise ValueError("common risk invariant changed")
    templates, aliases = contract["templates"], contract["preregistration_aliases"]
    requested = [name for hypothesis in prereg["hypothesis_search_spaces"]
                 for name in hypothesis["axes"]["exit_template"]]
    resolved = [aliases.get(name, name) for name in requested]
    if len(requested) != 18 or len(set(resolved)) != 18 or set(resolved) != set(templates):
        raise ValueError("exit templates do not map one-to-one to preregistration")
    for name, item in templates.items():
        if item["max_bars"] < 1 or not item.get("stop") or not item.get("target"):
            raise ValueError(f"incomplete exit geometry: {name}")
        manager = item.get("manager", {})
        if manager.get("kind") != "NONE" and manager.get("allow_widen", False):
            raise ValueError(f"manager can widen stop: {name}")
    return {"decision": "PASS_EXIT_CONTRACT", "templates": len(templates),
            "aliases": len(aliases), "performance_accessed": False,
            "holdout_accessed": False, "sqcli_authorized": False}


if __name__ == "__main__": print(json.dumps(verify(), sort_keys=True))
