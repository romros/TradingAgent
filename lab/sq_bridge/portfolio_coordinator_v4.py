#!/usr/bin/env python3
"""Coordinate preregistered campaigns into one deterministic v4 portfolio."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.portfolio_construction_v4 import (
    _source_hypothesis, build as build_portfolio,
)
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


STAGES = (
    ("screen-bootstrap/screen_trigger_receipt.json",
     {"PASS_SCREEN_TRIGGER"}, {"REJECT_SCREEN_TRIGGER"}),
    ("sq-worker/worker_receipt.json",
     {"PASS_SQ_GENERATION_ORCHESTRATED"}, {"REJECT_NO_SQ_CANDIDATES"}),
    ("temporal-worker/temporal_worker_receipt.json",
     {"PASS_TEMPORAL_VALIDATION"}, {"REJECT_TEMPORAL_VALIDATION"}),
    ("robustness-worker/robustness_worker_receipt.json",
     {"PASS_ROBUSTNESS"}, {"REJECT_ROBUSTNESS"}),
    ("small-account-worker/small_account_worker_receipt.json",
     {"PASS_SMALL_ACCOUNT"}, {"REJECT_SMALL_ACCOUNT"}),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _resolve(base: Path, value: object, digest: object | None,
             label: str, *, must_exist: bool = True) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} path missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if must_exist and (not path.is_file() or not isinstance(digest, str)
                       or _sha(path) != digest):
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _campaign_terminal(campaign_root: Path, campaign_id: str) -> tuple[
        str, Path, dict[str, Any]] | None:
    """Return the first terminal receipt, while enforcing sequential lineage."""
    passed: list[Path] = []
    for relative, pass_decisions, reject_decisions in STAGES:
        path = campaign_root / relative
        if not path.is_file():
            return None
        receipt = _load(path)
        decision = receipt.get("decision")
        if receipt.get("campaign_id") != campaign_id:
            raise ValueError(f"campaign receipt identity mismatch: {campaign_id}")
        if decision in reject_decisions:
            later = [campaign_root / row[0] for row in STAGES[len(passed) + 1:]]
            if any(item.is_file() for item in later):
                raise ValueError(f"receipts exist after terminal rejection: {campaign_id}")
            return str(decision), path, receipt
        if decision not in pass_decisions:
            raise ValueError(f"campaign receipt decision invalid: {campaign_id}")
        passed.append(path)
    return "PASS_SMALL_ACCOUNT", passed[-1], _load(passed[-1])


def tick(*, registry_path: Path, output_dir: Path,
         portfolio_fn: Callable[..., dict] = build_portfolio,
         hypothesis_fn: Callable[[dict, Path, str], str] = _source_hypothesis,
         ) -> dict[str, Any]:
    registry_path, output_dir = registry_path.resolve(), output_dir.resolve()
    registry = _load(registry_path)
    entries = registry.get("campaigns")
    if (registry.get("schema_version") != 1
            or not isinstance(registry.get("portfolio_id"), str)
            or not registry["portfolio_id"]
            or registry.get("registration_closed") not in {True, False}
            or not isinstance(entries, list) or not entries):
        raise ValueError("portfolio campaign registry invalid")
    methodology_path = _resolve(
        registry_path.parent, registry.get("methodology_path"),
        registry.get("methodology_sha256"), "portfolio methodology")
    universe_path = _resolve(
        registry_path.parent, registry.get("campaign_universe_path"),
        registry.get("campaign_universe_sha256"), "campaign universe")
    universe = _load(universe_path)
    campaign_ids = [row.get("campaign_id") for row in entries
                    if isinstance(row, dict)]
    if (len(campaign_ids) != len(entries)
            or any(not isinstance(value, str) or not value for value in campaign_ids)
            or campaign_ids != sorted(set(campaign_ids))):
        raise ValueError("registered campaign ids must be unique and sorted")
    universe_rows = universe.get("campaigns")
    universe_ids = ([row.get("campaign_id") for row in universe_rows]
                    if isinstance(universe_rows, list) else None)
    if (universe.get("schema_version") != 1
            or universe.get("registration_closed") is not True
            or universe.get("performance_accessed") is not False
            or universe.get("candidate_ids") != []
            or universe.get("holdout_accessed") is not False
            or universe_ids != campaign_ids):
        raise ValueError("campaign universe differs from portfolio registry")
    for row in universe_rows:
        mechanisms = row.get("mechanisms") if isinstance(row, dict) else None
        if (not isinstance(row.get("symbol"), str)
                or not isinstance(row.get("timeframe"), str)
                or row.get("category") not in {
                    "forex", "commodity", "crypto", "index", "stock"}
                or not isinstance(mechanisms, list) or len(mechanisms) != 3
                or len(set(mechanisms)) != 3
                or row.get("directions_per_mechanism") != ["both", "long", "short"]
                or not str(row.get("readiness", "")).startswith("WAITING_")):
            raise ValueError("campaign universe design invalid")

    terminal, pending, rejected, branches = {}, [], [], []
    for row in entries:
        campaign_id = row["campaign_id"]
        campaign_root = _resolve(
            registry_path.parent, row.get("campaign_root"), None,
            f"{campaign_id} campaign root", must_exist=False)
        found = _campaign_terminal(campaign_root, campaign_id)
        if found is None:
            pending.append(campaign_id)
            continue
        decision, receipt_path, receipt = found
        if decision != "PASS_SMALL_ACCOUNT":
            rejected.append(campaign_id)
            terminal[campaign_id] = {"decision": decision,
                                     "receipt_path": str(receipt_path),
                                     "receipt_sha256": _sha(receipt_path)}
            continue
        artifact_path = _resolve(
            receipt_path.parent, receipt.get("small_account_artifact_path"),
            receipt.get("small_account_artifact_sha256"),
            f"{campaign_id} small-account artifact")
        artifact = _load(artifact_path)
        ids = artifact.get("candidate_ids")
        if (artifact.get("stage") != "small_account_economics"
                or artifact.get("decision") != "PASS"
                or artifact.get("campaign_id") != campaign_id
                or artifact.get("holdout_accessed") is not False
                or not isinstance(ids, list) or len(ids) != 1):
            raise ValueError(f"small-account branch invalid: {campaign_id}")
        hypothesis_id = hypothesis_fn(artifact, artifact_path, ids[0])
        branches.append({
            "hypothesis_id": hypothesis_id, "campaign_id": campaign_id,
            "artifact_path": str(artifact_path),
            "artifact_sha256": _sha(artifact_path)})
        terminal[campaign_id] = {
            "decision": decision, "candidate_id": ids[0],
            "hypothesis_id": hypothesis_id, "receipt_path": str(receipt_path),
            "receipt_sha256": _sha(receipt_path),
            "artifact_path": str(artifact_path),
            "artifact_sha256": _sha(artifact_path)}

    status = {
        "schema_version": 1, "portfolio_id": registry["portfolio_id"],
        "registration_closed": registry["registration_closed"],
        "registered_campaign_ids": campaign_ids,
        "registry_path": str(registry_path),
        "registry_sha256": _sha(registry_path),
        "methodology_path": str(methodology_path),
        "methodology_sha256": _sha(methodology_path),
        "campaign_universe_path": str(universe_path),
        "campaign_universe_sha256": _sha(universe_path),
        "terminal_campaigns": terminal, "pending_campaign_ids": pending,
        "rejected_campaign_ids": rejected,
        "passing_branch_count": len(branches), "holdout_accessed": False,
        "paper_authorized": False, "live_authorized": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    if not registry["registration_closed"]:
        result = {**status, "decision": "WAITING_FOR_REGISTRATION_CLOSE"}
        write_atomic(output_dir / "portfolio_coordinator_status.json", result)
        return result
    if pending:
        result = {**status, "decision": "WAITING_FOR_REGISTERED_CAMPAIGNS"}
        write_atomic(output_dir / "portfolio_coordinator_status.json", result)
        return result

    manifest = {
        "schema_version": 1, "portfolio_id": registry["portfolio_id"],
        "holdout_accessed": False,
        "small_account_branches": sorted(
            branches, key=lambda row: (row["hypothesis_id"], row["campaign_id"])),
        "registry_path": str(registry_path), "registry_sha256": _sha(registry_path),
        "registered_campaign_ids": campaign_ids,
        "terminal_campaign_receipts": terminal,
    }
    manifest_path = output_dir / "portfolio_manifest.json"
    write_atomic(manifest_path, manifest)
    artifact_path = output_dir / "portfolio_construction.json"
    artifact = portfolio_fn(
        manifest_path=manifest_path, methodology_path=methodology_path,
        output_path=artifact_path)
    result = {
        **status,
        "decision": ("PASS_PORTFOLIO_CONSTRUCTION"
                     if artifact.get("decision") == "PASS"
                     else "REJECT_PORTFOLIO_CONSTRUCTION"),
        "candidate_ids": artifact.get("candidate_ids", []),
        "portfolio_manifest_path": str(manifest_path),
        "portfolio_manifest_sha256": _sha(manifest_path),
        "portfolio_artifact_path": str(artifact_path),
        "portfolio_artifact_sha256": _sha(artifact_path),
    }
    write_atomic(output_dir / "portfolio_coordinator_status.json", result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path,
                        default=Path(__file__).with_name("portfolio_registry_v4.json"))
    parser.add_argument("--output-dir", type=Path,
                        default=root / "data/alquimia_v4/portfolio")
    args = parser.parse_args()
    print(json.dumps(tick(registry_path=args.registry, output_dir=args.output_dir),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
