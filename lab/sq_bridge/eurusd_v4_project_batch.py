#!/usr/bin/env python3
"""Compile every authorized EURUSD v4 branch into verified, inert SQ CFX files."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build as build_project
from lab.sq_bridge.eurusd_sq_generation_plan_v4 import compile_plan
from lab.sq_bridge.sq_project_contract import verify_genetic_project
from lab.sq_bridge.temporal_split_contract_v4 import digest as temporal_digest
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_path(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha256(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _verified_contract(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    try:
        contract = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} path/hash mismatch") from exc
    if not isinstance(contract, dict) or temporal_digest(contract) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


PLAN_CONTRACT_KEYS = (
    "decision", "campaign_id", "chain_hypothesis_id", "source_hypothesis_id",
    "market", "project_name", "search_profile", "generation_type",
    "attempt_budget", "accepted_limit", "market_side", "maximum_rules",
    "date_from", "date_to", "periods", "holdout_sealed",
)


def _recompile_plan(plan: dict, chain_path: Path, methodology_path: Path,
                    output_dir: Path, compile_plan_fn) -> dict:
    screen_path = _verified_path(
        plan.get("screen_artifact_path"), plan.get("screen_artifact_sha256"),
        "screen artifact")
    with tempfile.TemporaryDirectory(prefix="plan-audit-", dir=output_dir) as temporary:
        root = Path(temporary)
        return compile_plan_fn(
            screen_path=screen_path, chain_path=chain_path,
            methodology_path=methodology_path,
            period_contract_output=root / "periods.json",
            plan_output=root / "plan.json")


def _verify_project_row(hypothesis_id: str, row: object) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f"invalid completed project row: {hypothesis_id}")
    cfx = _verified_path(row.get("project_cfx_path"),
                         row.get("project_cfx_sha256"),
                         f"{hypothesis_id} completed CFX")
    manifest_path = _verified_path(
        row.get("project_manifest_path"), row.get("project_manifest_sha256"),
        f"{hypothesis_id} completed manifest")
    manifest = json.loads(manifest_path.read_text())
    shape = verify_genetic_project(cfx, manifest)
    if (manifest.get("project_name") != row.get("project_name")
            or shape != row.get("sq_genetic_shape")):
        raise ValueError(f"{hypothesis_id} completed project contract mismatch")
    return row


def _completed_batch(path: Path, *, bootstrap_path: Path, scaffold_path: Path,
                     registry_path: Path, methodology_path: Path,
                     selected: list[str]) -> dict:
    result = json.loads(path.read_text())
    projects = result.get("projects")
    if (result.get("decision") != "PASS_CFX_BATCH_READY"
            or result.get("bootstrap_path") != str(bootstrap_path)
            or result.get("bootstrap_sha256") != _sha256(bootstrap_path)
            or result.get("scaffold_path") != str(scaffold_path)
            or result.get("scaffold_sha256") != _sha256(scaffold_path)
            or result.get("registry_path") != str(registry_path)
            or result.get("registry_sha256") != _sha256(registry_path)
            or result.get("methodology_path") != str(methodology_path)
            or result.get("methodology_sha256") != _sha256(methodology_path)
            or result.get("selected_hypothesis_ids") != sorted(selected)
            or result.get("sqcli_started") is not False
            or not isinstance(projects, dict)
            or set(projects) != set(selected)):
        raise ValueError("completed project batch does not match frozen inputs")
    for hypothesis_id, row in projects.items():
        _verify_project_row(hypothesis_id, row)
    return result


def compile_projects(*, bootstrap_path: Path, scaffold_path: Path,
                     registry_path: Path, methodology_path: Path,
                     output_dir: Path, market_key: str = "EURUSD",
                     compile_plan_fn=None) -> dict:
    for path in (bootstrap_path, scaffold_path, registry_path, methodology_path):
        if not path.resolve().is_file():
            raise ValueError(f"missing input: {path}")
    bootstrap_path, scaffold_path, registry_path, methodology_path = (
        path.resolve() for path in (
            bootstrap_path, scaffold_path, registry_path, methodology_path))
    bootstrap = json.loads(bootstrap_path.read_text())
    compile_plan_fn = compile_plan if compile_plan_fn is None else compile_plan_fn
    if market_key not in {"EURUSD", "US500"}:
        raise ValueError("unsupported v4 SQ batch market")
    branches = bootstrap.get("branches")
    selected = bootstrap.get("selected_hypothesis_ids")
    if (bootstrap.get("decision") != "PASS_SQ_BRANCHES_READY"
            or bootstrap.get("sqcli_started") is not False
            or not isinstance(branches, dict) or not branches
            or not isinstance(selected, list) or sorted(branches) != sorted(selected)
            or len(selected) != len(set(selected))):
        raise ValueError("bootstrap does not authorize SQ project compilation")

    output_dir.mkdir(parents=True, exist_ok=True)
    validated = {}
    for hypothesis_id in sorted(branches):
        branch = branches[hypothesis_id]
        if not isinstance(branch, dict):
            raise ValueError(f"invalid branch: {hypothesis_id}")
        plan_path = _verified_path(
            branch.get("generation_plan_path"), branch.get("generation_plan_sha256"),
            f"{hypothesis_id} plan")
        chain_path = _verified_path(
            branch.get("chain_path"), branch.get("chain_sha256"),
            f"{hypothesis_id} chain")
        plan = json.loads(plan_path.read_text())
        expected_plan = _recompile_plan(
            plan, chain_path, methodology_path, output_dir, compile_plan_fn)
        if any(plan.get(key) != expected_plan.get(key) for key in PLAN_CONTRACT_KEYS):
            raise ValueError(f"{hypothesis_id} plan differs from independent compilation")
        contract_path = _verified_contract(
            plan.get("temporal_split_contract_path"),
            plan.get("temporal_split_contract_sha256"), f"{hypothesis_id} periods")
        if (plan.get("decision") != "PASS_GENERATION_PLAN"
                or plan.get("source_hypothesis_id") != hypothesis_id
                or plan.get("chain_hypothesis_id") != hypothesis_id
                or plan.get("market") != market_key
                or plan.get("generation_type") != "genetic-evolution"
                or plan.get("evidence_chain_path") != str(chain_path)
                or plan.get("evidence_chain_sha256") != _sha256(chain_path)
                or branch.get("search_profile") != plan.get("search_profile")):
            raise ValueError(f"{hypothesis_id} generation plan mismatch")
        validated[hypothesis_id] = (plan, chain_path, contract_path)

    projects = {}
    final_path = output_dir / "project_batch.json"
    checkpoint_path = output_dir / "project_batch_checkpoint.json"
    if final_path.is_file():
        return _completed_batch(
            final_path, bootstrap_path=bootstrap_path,
            scaffold_path=scaffold_path, registry_path=registry_path,
            methodology_path=methodology_path, selected=selected)
    checkpoint_contract = {
        "schema_version": 1, "bootstrap_path": str(bootstrap_path),
        "bootstrap_sha256": _sha256(bootstrap_path),
        "scaffold_path": str(scaffold_path),
        "scaffold_sha256": _sha256(scaffold_path),
        "registry_path": str(registry_path), "registry_sha256": _sha256(registry_path),
        "methodology_path": str(methodology_path),
        "methodology_sha256": _sha256(methodology_path),
        "selected_hypothesis_ids": sorted(selected),
        "projects": {}, "sqcli_started": False,
    }
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text())
        expected = {**checkpoint_contract, "projects": checkpoint.get("projects")}
        if (not isinstance(checkpoint.get("projects"), dict)
                or checkpoint != expected):
            raise ValueError("project batch checkpoint does not match frozen inputs")
    else:
        unexpected = sorted(path.name for path in output_dir.iterdir())
        if unexpected:
            raise ValueError(f"project batch output has no checkpoint: {unexpected}")
        checkpoint = checkpoint_contract
        write_atomic(checkpoint_path, checkpoint)
    for hypothesis_id in sorted(validated):
        plan, chain_path, contract_path = validated[hypothesis_id]
        branch_output = output_dir / hypothesis_id
        project_path = branch_output / "project.cfx"
        checkpoint_row = checkpoint["projects"].get(hypothesis_id)
        if checkpoint_row is not None:
            if (not isinstance(checkpoint_row, dict)
                    or checkpoint_row.get("state") != "VERIFIED"):
                raise ValueError(f"invalid project checkpoint row: {hypothesis_id}")
            projects[hypothesis_id] = _verify_project_row(
                hypothesis_id, checkpoint_row.get("project"))
            continue
        manifest = build_project(
            source=scaffold_path, output=project_path,
            project_name=plan["project_name"], market_key=market_key,
            registry_path=registry_path, methodology_path=methodology_path,
            date_from=date.fromisoformat(plan["date_from"]),
            date_to=date.fromisoformat(plan["date_to"]),
            accepted_limit=plan["accepted_limit"],
            search_profile=plan["search_profile"],
            generation_type=plan["generation_type"],
            attempt_budget=plan["attempt_budget"], market_side=plan["market_side"],
            evidence_chain_path=chain_path, campaign_id=plan["campaign_id"],
            source_hypothesis_id=hypothesis_id,
            period_contract_path=contract_path)
        shape = verify_genetic_project(project_path, manifest)
        manifest_path = project_path.with_suffix(".manifest.json")
        if (manifest.get("project_name") != plan.get("project_name")
                or manifest.get("attempt_budget") != plan.get("attempt_budget")
                or manifest.get("search_profile") != plan.get("search_profile")
                or manifest.get("evidence_chain_sha256") != _sha256(chain_path)):
            raise ValueError(f"{hypothesis_id} compiled manifest mismatch")
        projects[hypothesis_id] = {
            "project_name": manifest["project_name"],
            "project_cfx_path": str(project_path.resolve()),
            "project_cfx_sha256": _sha256(project_path),
            "project_manifest_path": str(manifest_path.resolve()),
            "project_manifest_sha256": _sha256(manifest_path),
            "sq_genetic_shape": shape,
        }
        checkpoint["projects"][hypothesis_id] = {
            "state": "VERIFIED", "project": projects[hypothesis_id],
        }
        write_atomic(checkpoint_path, checkpoint)

    result = {
        "schema_version": 1, "decision": "PASS_CFX_BATCH_READY",
        "campaign_id": bootstrap.get("campaign_id"),
        "bootstrap_path": str(bootstrap_path),
        "bootstrap_sha256": _sha256(bootstrap_path),
        "scaffold_path": str(scaffold_path), "scaffold_sha256": _sha256(scaffold_path),
        "registry_path": str(registry_path), "registry_sha256": _sha256(registry_path),
        "methodology_path": str(methodology_path),
        "methodology_sha256": _sha256(methodology_path),
        "selected_hypothesis_ids": sorted(selected), "projects": projects,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", required=True, type=Path)
    parser.add_argument("--scaffold", required=True, type=Path)
    parser.add_argument("--registry", type=Path,
                        default=Path(__file__).with_name("ostium_markets.json"))
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = compile_projects(
        bootstrap_path=args.bootstrap, scaffold_path=args.scaffold,
        registry_path=args.registry, methodology_path=args.methodology,
        output_dir=args.output_dir)
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"]),
                      "sqcli_started": result["sqcli_started"]}, indent=2))


if __name__ == "__main__":
    main()
