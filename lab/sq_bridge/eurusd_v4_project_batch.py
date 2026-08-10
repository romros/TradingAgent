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
                    output_dir: Path) -> dict:
    screen_path = _verified_path(
        plan.get("screen_artifact_path"), plan.get("screen_artifact_sha256"),
        "screen artifact")
    with tempfile.TemporaryDirectory(prefix="plan-audit-", dir=output_dir) as temporary:
        root = Path(temporary)
        return compile_plan(
            screen_path=screen_path, chain_path=chain_path,
            methodology_path=methodology_path,
            period_contract_output=root / "periods.json",
            plan_output=root / "plan.json")


def compile_projects(*, bootstrap_path: Path, scaffold_path: Path,
                     registry_path: Path, methodology_path: Path,
                     output_dir: Path) -> dict:
    for path in (bootstrap_path, scaffold_path, registry_path, methodology_path):
        if not path.resolve().is_file():
            raise ValueError(f"missing input: {path}")
    bootstrap_path, scaffold_path, registry_path, methodology_path = (
        path.resolve() for path in (
            bootstrap_path, scaffold_path, registry_path, methodology_path))
    bootstrap = json.loads(bootstrap_path.read_text())
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
            plan, chain_path, methodology_path, output_dir)
        if any(plan.get(key) != expected_plan.get(key) for key in PLAN_CONTRACT_KEYS):
            raise ValueError(f"{hypothesis_id} plan differs from independent compilation")
        contract_path = _verified_contract(
            plan.get("temporal_split_contract_path"),
            plan.get("temporal_split_contract_sha256"), f"{hypothesis_id} periods")
        if (plan.get("decision") != "PASS_GENERATION_PLAN"
                or plan.get("source_hypothesis_id") != hypothesis_id
                or plan.get("chain_hypothesis_id") != hypothesis_id
                or plan.get("market") != "EURUSD"
                or plan.get("generation_type") != "genetic-evolution"
                or plan.get("evidence_chain_path") != str(chain_path)
                or plan.get("evidence_chain_sha256") != _sha256(chain_path)
                or branch.get("search_profile") != plan.get("search_profile")):
            raise ValueError(f"{hypothesis_id} generation plan mismatch")
        validated[hypothesis_id] = (plan, chain_path, contract_path)

    projects = {}
    collisions = [output_dir / "project_batch.json"] + [
        output_dir / hypothesis_id for hypothesis_id in validated]
    if any(path.exists() for path in collisions):
        raise ValueError("project batch output collision; use a fresh output directory")
    for hypothesis_id in sorted(validated):
        plan, chain_path, contract_path = validated[hypothesis_id]
        branch_output = output_dir / hypothesis_id
        project_path = branch_output / "project.cfx"
        manifest = build_project(
            source=scaffold_path, output=project_path,
            project_name=plan["project_name"], market_key="EURUSD",
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

    result = {
        "schema_version": 1, "decision": "PASS_CFX_BATCH_READY",
        "campaign_id": bootstrap.get("campaign_id"),
        "bootstrap_path": str(bootstrap_path),
        "bootstrap_sha256": _sha256(bootstrap_path),
        "scaffold_path": str(scaffold_path), "scaffold_sha256": _sha256(scaffold_path),
        "selected_hypothesis_ids": sorted(selected), "projects": projects,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(output_dir / "project_batch.json", result)
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
