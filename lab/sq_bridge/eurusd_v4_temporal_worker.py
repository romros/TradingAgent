#!/usr/bin/env python3
"""Resume the verified EURUSD SQ universe through global temporal Pareto."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.sq_temporal_stage_v4 import run_stage
from lab.sq_bridge.sqcli_transport import list_projects_with_status
from lab.sq_bridge.temporal_split_contract_v4 import digest as temporal_digest
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verified(value: object, digest: object, label: str,
              base: Path | None = None) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else ((base or Path.cwd()) / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _running(rows: list[dict]) -> list[str]:
    return sorted(str(row.get("projectName")) for row in rows
                  if row.get("runningStatus") not in {None, 0})


def _own_resumable_project(work_dir: Path, running: list[str]) -> bool:
    if len(running) != 1:
        return False
    receipts = list(work_dir.glob("*/run/retest_preflight.json"))
    names = []
    for path in receipts:
        try:
            value = _load(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if value.get("decision") == "PASS_RETEST_PREFLIGHT":
            names.append(value.get("project_name"))
    return running == names[-1:] or running[0] in names


def tick(*, screen_dir: Path, sq_worker_dir: Path, output_dir: Path,
         worker_config_path: Path,
         listing_fn: Callable[..., list[dict]] = list_projects_with_status,
         temporal_fn: Callable[..., dict] = run_stage) -> dict[str, Any]:
    screen_receipt_path = screen_dir.resolve() / "screen_trigger_receipt.json"
    worker_receipt_path = sq_worker_dir.resolve() / "worker_receipt.json"
    if not worker_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_SQ_GENERATION",
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    worker = _load(worker_receipt_path)
    campaign_id = worker.get("campaign_id")
    if worker.get("decision") == "REJECT_NO_SQ_CANDIDATES":
        return {"schema_version": 1, "decision": "REJECT_NO_SQ_CANDIDATES",
                "campaign_id": campaign_id, "candidate_ids": [],
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    if worker.get("decision") != "PASS_SQ_GENERATION_ORCHESTRATED":
        raise ValueError("unsupported SQ worker decision")
    universe_path = _verified(
        worker.get("global_generation_artifact_path"),
        worker.get("global_generation_artifact_sha256"), "global SQ universe")
    universe = _load(universe_path)
    if (universe.get("decision") != "PASS"
            or universe.get("campaign_id") != campaign_id
            or universe.get("candidate_ids") != worker.get("candidate_ids")
            or universe.get("artifact_role")
                != "global_multi_branch_candidate_universe"):
        raise ValueError("global SQ universe does not match worker receipt")

    screen = _load(screen_receipt_path)
    bootstrap_path = _verified(
        screen.get("bootstrap_path"), screen.get("bootstrap_sha256"), "bootstrap")
    bootstrap = _load(bootstrap_path)
    if (screen.get("decision") != "PASS_SCREEN_TRIGGER"
            or screen.get("campaign_id") != campaign_id
            or bootstrap.get("campaign_id") != campaign_id):
        raise ValueError("screen/bootstrap identity mismatch")
    preflight_path = _verified(
        screen.get("frozen_preflight_path"), screen.get("frozen_preflight_sha256"),
        "preflight")
    preflight = _load(preflight_path)
    costs = (preflight.get("input_receipts") or {}).get("costs") or {}
    cost_model_path = _verified(costs.get("path"), costs.get("sha256"), "cost model")

    branches = bootstrap.get("branches")
    if not isinstance(branches, dict) or not branches:
        raise ValueError("bootstrap branches missing")
    temporal_contract_path = None
    temporal_contract_hash = None
    for hypothesis_id in sorted(branches):
        branch = branches[hypothesis_id]
        plan_path = _verified(branch.get("generation_plan_path"),
                              branch.get("generation_plan_sha256"),
                              f"{hypothesis_id} generation plan")
        plan = _load(plan_path)
        contract_path = Path(str(plan.get("temporal_split_contract_path", ""))).resolve()
        try:
            contract = _load(contract_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{hypothesis_id} temporal contract missing") from exc
        digest = temporal_digest(contract)
        if digest != plan.get("temporal_split_contract_sha256"):
            raise ValueError(f"{hypothesis_id} temporal contract hash mismatch")
        if temporal_contract_hash is None:
            temporal_contract_path, temporal_contract_hash = contract_path, digest
        elif digest != temporal_contract_hash:
            raise ValueError("SQ branches use different temporal contracts")

    batch_path = sq_worker_dir.resolve() / "cfx_batch/project_batch.json"
    batch = _load(batch_path)
    projects = batch.get("projects")
    first_id = sorted(branches)[0]
    if (batch.get("decision") != "PASS_CFX_BATCH_READY"
            or batch.get("campaign_id") != campaign_id
            or not isinstance(projects, dict) or set(projects) != set(branches)):
        raise ValueError("SQ project batch mismatch")
    first = projects[first_id]
    discovery_manifest = _verified(
        first.get("project_manifest_path"), first.get("project_manifest_sha256"),
        "discovery manifest")
    resource_source = _verified(
        first.get("project_cfx_path"), first.get("project_cfx_sha256"),
        "discovery resource")
    methodology_path = _verified(
        screen.get("methodology_path"), screen.get("methodology_sha256"),
        "methodology")
    methodology = _load(methodology_path)
    selected_hypotheses = screen.get("selected_hypothesis_ids")
    if (not isinstance(selected_hypotheses, list)
            or universe.get("expected_hypothesis_ids") != sorted(selected_hypotheses)
            or universe.get("source_hypothesis_ids") != sorted(selected_hypotheses)
            or set(universe.get("source_generation_artifacts") or {})
                != set(selected_hypotheses)
            or universe.get("global_candidate_budget")
                != (methodology.get("sq_generation") or {}).get(
                    "accepted_candidates_global_budget")):
        raise ValueError("global SQ universe is not bound to frozen screen/budget")
    config = _load(worker_config_path.resolve())
    template = _verified(config.get("scaffold_path"), config.get("scaffold_sha256"),
                         "Retest template", worker_config_path.resolve().parent)

    final_path = output_dir.resolve() / "04_temporal_validation.json"
    receipt_path = output_dir.resolve() / "temporal_worker_receipt.json"
    if receipt_path.is_file():
        result = _load(receipt_path)
        artifact = _verified(result.get("temporal_artifact_path"),
                             result.get("temporal_artifact_sha256"),
                             "temporal artifact")
        if (result.get("campaign_id") != campaign_id
                or artifact != final_path
                or result.get("decision") not in {
                    "PASS_TEMPORAL_VALIDATION", "REJECT_TEMPORAL_VALIDATION"}):
            raise ValueError("completed temporal worker receipt invalid")
        return result

    work_dir = output_dir.resolve() / "retests"
    running = _running(listing_fn(config["base_url"]))
    if running and not _own_resumable_project(work_dir, running):
        return {"schema_version": 1, "decision": "WAITING_FOR_SQCLI_IDLE",
                "campaign_id": campaign_id, "running_projects": running,
                "sqcli_started": False, "paper_authorized": False,
                "live_authorized": False}
    artifact = temporal_fn(
        campaign_id=campaign_id, generation_artifact_path=universe_path,
        retest_template_path=template, discovery_manifest_path=discovery_manifest,
        temporal_contract_path=temporal_contract_path,
        methodology_path=methodology_path, cost_model_path=cost_model_path,
        symbol="EURUSD", timeframe="D1", source_timezone="Etc/UTC",
        work_dir=work_dir, artifact_path=final_path,
        resource_source_path=resource_source, resource_task_file="Build-Task1.xml",
        slippage=0, test_precision=4)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise ValueError("temporal stage returned an invalid decision")
    evaluated_ids = sorted(
        (artifact.get("evaluated_candidate_temporal_metrics") or {}).keys())
    if (evaluated_ids != universe["candidate_ids"]
            or any(value not in evaluated_ids
                   for value in artifact.get("candidate_ids", []))):
        raise ValueError("temporal Pareto did not evaluate the complete SQ universe")
    result = {
        "schema_version": 1,
        "decision": ("PASS_TEMPORAL_VALIDATION" if artifact["decision"] == "PASS"
                     else "REJECT_TEMPORAL_VALIDATION"),
        "campaign_id": campaign_id, "candidate_ids": artifact.get("candidate_ids", []),
        "evaluated_candidate_ids": sorted(
            (artifact.get("evaluated_candidate_temporal_metrics") or {}).keys()),
        "temporal_artifact_path": str(final_path),
        "temporal_artifact_sha256": _sha(final_path),
        "global_generation_artifact_path": str(universe_path),
        "global_generation_artifact_sha256": _sha(universe_path),
        "holdout_accessed": False, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(receipt_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-dir", type=Path,
                        default=campaign / "screen-bootstrap")
    parser.add_argument("--sq-worker-dir", type=Path, default=campaign / "sq-worker")
    parser.add_argument("--output-dir", type=Path, default=campaign / "temporal-worker")
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    args = parser.parse_args()
    print(json.dumps(tick(
        screen_dir=args.screen_dir, sq_worker_dir=args.sq_worker_dir,
        output_dir=args.output_dir, worker_config_path=args.worker_config),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
