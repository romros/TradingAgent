#!/usr/bin/env python3
"""Compile every replay-selected crypto H4 region into inert native SQ CFX files."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_cfx_v4 import compile_cfx, verify_cfx
from lab.sq_bridge.crypto_h4_sq_generation_plan_v4 import compile_plan
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


CANDIDATE_ID = re.compile(r"^alq4_[0-9a-f]{16}$")
SUPPORTED_MECHANISMS = {"channel_breakout", "time_series_momentum"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _file(path: Path, digest: object, label: str) -> Path:
    path = path.resolve()
    if not path.is_file() or not isinstance(digest, str) or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _inputs(selector: Path, design: Path, semantics: Path, scaffold: Path,
            resources: dict[str, Path]) -> dict[str, dict[str, str]]:
    values = {"selector": selector, "design": design, "semantics": semantics,
              "scaffold": scaffold, **{f"{key.lower()}_resource": value
                                       for key, value in resources.items()}}
    return {key: {"path": str(path), "sha256": _sha(path)}
            for key, path in values.items()}


def verify_project_row(candidate_id: str, row: object,
                       frozen_inputs: dict[str, dict[str, str]]) -> dict[str, Any]:
    if not isinstance(row, dict) or row.get("candidate_id") != candidate_id:
        raise ValueError(f"invalid completed crypto project row: {candidate_id}")
    plan_path = _file(Path(str(row.get("plan_path"))), row.get("plan_sha256"),
                      f"{candidate_id} plan")
    manifest_path = _file(Path(str(row.get("manifest_path"))),
                          row.get("manifest_sha256"), f"{candidate_id} manifest")
    cfx_path = _file(Path(str(row.get("cfx_path"))), row.get("cfx_sha256"),
                     f"{candidate_id} CFX")
    plan, manifest = _load(plan_path), _load(manifest_path)
    verification = verify_cfx(cfx_path, manifest)
    resource_key = f"{str(plan.get('market')).lower()}_resource"
    expected_plan_inputs = {
        "selector": frozen_inputs["selector"],
        "design": frozen_inputs["design"],
        "semantics": frozen_inputs["semantics"],
        "sq_resource": frozen_inputs[resource_key],
    }
    if (plan.get("decision") != "PASS_SQ_PLAN_READY"
            or plan.get("candidate_id") != candidate_id
            or any(plan.get("inputs", {}).get(key) != value
                   for key, value in expected_plan_inputs.items())
            or manifest.get("candidate_id") != candidate_id
            or manifest.get("plan_sha256") != _sha(plan_path)
            or manifest.get("format_scaffold_path") != frozen_inputs["scaffold"]["path"]
            or manifest.get("format_scaffold_sha256") != frozen_inputs["scaffold"]["sha256"]
            or row.get("project_name") != plan.get("project_name")
            or row.get("sqcli_started") is not False
            or list(verification["shape"]) != row.get("genetic_shape")):
        raise ValueError(f"{candidate_id} completed crypto project contract mismatch")
    return row


def compile_batch(*, selector_path: Path, design_path: Path, semantics_path: Path,
                  scaffold_path: Path, btc_resource_path: Path,
                  eth_resource_path: Path, output_dir: Path) -> dict[str, Any]:
    selector_path, design_path, semantics_path, scaffold_path = (
        path.resolve() for path in
        (selector_path, design_path, semantics_path, scaffold_path))
    resources = {"BTCUSD": btc_resource_path.resolve(),
                 "ETHUSD": eth_resource_path.resolve()}
    required = [selector_path, design_path, semantics_path, scaffold_path,
                *resources.values()]
    if any(not path.is_file() for path in required):
        raise ValueError("crypto CFX batch input missing")
    selector = _load(selector_path)
    regions = selector.get("selected_regions")
    selected = selector.get("selected_candidate_ids")
    if (selector.get("decision") != "PASS_STABLE_REGIONS"
            or selector.get("replay_verified") is not True
            or selector.get("sqcli_started") is not False
            or selector.get("validation_accessed") is not False
            or selector.get("oos_accessed") is not False
            or selector.get("holdout_accessed") is not False
            or not isinstance(regions, list) or not regions
            or not isinstance(selected, list)
            or selected != [row.get("candidate_id") for row in regions]
            or len(selected) != len(set(selected))
            or any(not isinstance(value, str) or not CANDIDATE_ID.fullmatch(value)
                   for value in selected)):
        raise ValueError("selector does not authorize crypto CFX batch")
    unsupported = sorted({row.get("mechanism") for row in regions}
                         - SUPPORTED_MECHANISMS)
    if unsupported:
        raise ValueError(f"UNTRANSLATED_SELECTED_MECHANISMS: {unsupported}")
    if any(row.get("market") not in resources for row in regions):
        raise ValueError("selected crypto market has no certified SQ resource")

    frozen_inputs = _inputs(selector_path, design_path, semantics_path,
                            scaffold_path, resources)
    output_dir = output_dir.resolve()
    final_path = output_dir / "crypto_h4_project_batch.json"
    checkpoint_path = output_dir / "crypto_h4_project_batch_checkpoint.json"
    if final_path.is_file():
        result = _load(final_path)
        if (result.get("decision") != "PASS_CRYPTO_CFX_BATCH_READY"
                or result.get("inputs") != frozen_inputs
                or result.get("selected_candidate_ids") != selected
                or result.get("translation_scope") != "sq_proposal_generation_only"
                or result.get("python_parity_required") is not True
                or result.get("strategy_promotion_authorized") is not False
                or result.get("sqcli_started") is not False
                or set(result.get("projects") or {}) != set(selected)):
            raise ValueError("completed crypto CFX batch changed")
        for candidate_id, row in result["projects"].items():
            verify_project_row(candidate_id, row, frozen_inputs)
        return result

    contract = {"schema_version": 1, "inputs": frozen_inputs,
                "selected_candidate_ids": selected, "projects": {},
                "sqcli_started": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    if checkpoint_path.is_file():
        checkpoint = _load(checkpoint_path)
        expected = {**contract, "projects": checkpoint.get("projects")}
        if not isinstance(checkpoint.get("projects"), dict) or checkpoint != expected:
            raise ValueError("crypto CFX batch checkpoint changed")
    else:
        unexpected = sorted(path.name for path in output_dir.iterdir())
        if unexpected:
            raise ValueError(f"crypto CFX output has no checkpoint: {unexpected}")
        checkpoint = contract
        write_atomic(checkpoint_path, checkpoint)

    by_id = {row["candidate_id"]: row for row in regions}
    projects: dict[str, dict[str, Any]] = {}
    for candidate_id in selected:
        saved = checkpoint["projects"].get(candidate_id)
        if saved is not None:
            if not isinstance(saved, dict) or saved.get("state") != "VERIFIED":
                raise ValueError(f"invalid crypto CFX checkpoint: {candidate_id}")
            projects[candidate_id] = verify_project_row(
                candidate_id, saved.get("project"), frozen_inputs)
            continue
        region = by_id[candidate_id]
        branch_dir = output_dir / candidate_id
        plan_path = branch_dir / "sq_plan.json"
        cfx_path = branch_dir / "project.cfx"
        plan = compile_plan(
            selector_path=selector_path, candidate_id=candidate_id,
            design_path=design_path, semantics_path=semantics_path,
            sq_resource_path=resources[region["market"]], output_path=plan_path)
        manifest = compile_cfx(plan_path, scaffold_path, cfx_path)
        manifest_path = cfx_path.with_suffix(".manifest.json")
        verification = verify_cfx(cfx_path, manifest)
        row = {"candidate_id": candidate_id, "market": plan["market"],
               "mechanism": plan["mechanism"], "direction": plan["direction"],
               "project_name": plan["project_name"],
               "plan_path": str(plan_path.resolve()), "plan_sha256": _sha(plan_path),
               "cfx_path": str(cfx_path.resolve()), "cfx_sha256": _sha(cfx_path),
               "manifest_path": str(manifest_path.resolve()),
               "manifest_sha256": _sha(manifest_path),
               "genetic_shape": list(verification["shape"]),
               "sqcli_started": False}
        projects[candidate_id] = row
        checkpoint["projects"][candidate_id] = {"state": "VERIFIED", "project": row}
        write_atomic(checkpoint_path, checkpoint)

    result = {"schema_version": 1, "stage": "crypto_h4_cfx_batch",
              "decision": "PASS_CRYPTO_CFX_BATCH_READY", "inputs": frozen_inputs,
              "selected_candidate_ids": selected, "projects": projects,
              "translation_scope": "sq_proposal_generation_only",
              "python_parity_required": True,
              "strategy_promotion_authorized": False,
              "sqcli_started": False, "paper_authorized": False,
              "live_authorized": False, "performance_accessed": False}
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector", required=True, type=Path)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--semantics", required=True, type=Path)
    parser.add_argument("--scaffold", required=True, type=Path)
    parser.add_argument("--btc-resource", required=True, type=Path)
    parser.add_argument("--eth-resource", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = compile_batch(
        selector_path=args.selector, design_path=args.design,
        semantics_path=args.semantics, scaffold_path=args.scaffold,
        btc_resource_path=args.btc_resource, eth_resource_path=args.eth_resource,
        output_dir=args.output_dir)
    print(json.dumps({"decision": result["decision"],
                      "selected_candidate_ids": result["selected_candidate_ids"],
                      "sqcli_started": result["sqcli_started"]}, indent=2))


if __name__ == "__main__":
    main()
