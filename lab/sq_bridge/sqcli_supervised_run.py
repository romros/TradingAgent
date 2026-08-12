#!/usr/bin/env python3
"""Start exactly one imported SQ project and preserve supervised run evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sq_project_contract import verify_genetic_project
from lab.sq_bridge.sq_watchdog import (
    gui_snapshot, load_limits, run_monitor, write_atomic,
)
from lab.sq_bridge.sqcli_transport import (
    docker_project_final_stats, gui_project_action_from_cli, gui_start_project,
    list_projects_with_status,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verified_file(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha256(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _completed_receipt(path: Path, hypothesis_id: str, project: str) -> dict:
    result = json.loads(path.read_text())
    if (result.get("decision") not in {
            "PASS_SUPERVISED_SQ_RUN", "FAIL_SUPERVISED_SQ_RUN"}
            or result.get("hypothesis_id") != hypothesis_id
            or result.get("project_name") != project):
        raise ValueError("completed run receipt identity mismatch")
    _verified_file(result.get("preflight_path"), result.get("preflight_sha256"),
                   "completed run preflight")
    _verified_file(result.get("start_receipt_path"), result.get("start_receipt_sha256"),
                   "completed run start receipt")
    _verified_file(result.get("watchdog_status_path"),
                   result.get("watchdog_status_sha256"), "completed run watchdog status")
    _verified_file(result.get("watchdog_journal_path"),
                   result.get("watchdog_journal_sha256"), "completed run watchdog journal")
    return result


def supervised_run(
    *, import_receipt_path: Path, hypothesis_id: str, output_dir: Path,
    base_url: str = "http://127.0.0.1:8080", container: str = "sqcli-docker",
    projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
    disk_path: Path = Path("/mnt/volume-SQ"), interval: int = 5,
    listing_fn: Callable[..., list[dict]] = list_projects_with_status,
    start_fn: Callable[..., dict] = gui_start_project,
    monitor_fn: Callable[..., dict] = run_monitor,
) -> dict:
    """Validate lineage, start one clean project, then block until exact final evidence."""
    if not isinstance(hypothesis_id, str) or not hypothesis_id:
        raise ValueError("hypothesis id missing")
    receipt_path = import_receipt_path.resolve()
    receipt = json.loads(receipt_path.read_text())
    projects = receipt.get("projects")
    if (receipt.get("decision") != "PASS_SQCLI_IMPORT"
            or receipt.get("sqcli_started") is not False
            or not isinstance(projects, dict) or hypothesis_id not in projects):
        raise ValueError("import receipt does not authorize this run")
    checkpoint_path = _verified_file(
        receipt.get("checkpoint_path"), receipt.get("checkpoint_sha256"),
        "import checkpoint")
    checkpoint = json.loads(checkpoint_path.read_text())
    if (checkpoint.get("batch_sha256") != receipt.get("batch_sha256")
            or not isinstance(checkpoint.get("projects"), dict)
            or set(checkpoint["projects"]) != set(projects)
            or any(not isinstance(row, dict) or row.get("state") != "VERIFIED"
                   or row.get("source_cfx_sha256")
                        != projects[hypothesis].get("source_cfx_sha256")
                   or row.get("sq_imported_cfx_sha256")
                        != projects[hypothesis].get("sq_imported_cfx_sha256")
                   for hypothesis, row in checkpoint["projects"].items())):
        raise ValueError("import checkpoint is incomplete or mismatched")
    imported = projects[hypothesis_id]
    batch_path = _verified_file(
        receipt.get("batch_path"), receipt.get("batch_sha256"), "source batch")
    batch = json.loads(batch_path.read_text())
    source = (batch.get("projects") or {}).get(hypothesis_id)
    if not isinstance(source, dict):
        raise ValueError("hypothesis missing from source batch")
    manifest_path = _verified_file(
        source.get("project_manifest_path"), source.get("project_manifest_sha256"),
        "project manifest")
    manifest = json.loads(manifest_path.read_text())
    imported_cfx = _verified_file(
        imported.get("sq_imported_cfx_path"), imported.get("sq_imported_cfx_sha256"),
        "SQ imported CFX")
    project = imported.get("project_name")
    if (project != source.get("project_name")
            or imported.get("source_cfx_sha256") != source.get("project_cfx_sha256")
            or imported.get("has_unresolved_resources") is not False
            or verify_genetic_project(imported_cfx, manifest) != source.get("sq_genetic_shape")):
        raise ValueError("imported project lineage/contract mismatch")

    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise ValueError("monitor interval must be positive")
    output_dir = output_dir.resolve()
    preflight = {
        "schema_version": 1, "decision": "PASS_SUPERVISED_RUN_PREFLIGHT",
        "hypothesis_id": hypothesis_id, "project_name": project,
        "import_receipt_path": str(receipt_path),
        "import_receipt_sha256": _sha256(receipt_path),
        "project_manifest_path": str(manifest_path),
        "project_manifest_sha256": _sha256(manifest_path),
        "sq_imported_cfx_path": str(imported_cfx),
        "sq_imported_cfx_sha256": _sha256(imported_cfx),
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    preflight_path = output_dir / "run_preflight.json"
    start_receipt_path = output_dir / "start_receipt.json"
    final_receipt_path = output_dir / "supervised_run_receipt.json"
    if final_receipt_path.is_file():
        return _completed_receipt(final_receipt_path, hypothesis_id, project)
    resuming = output_dir.exists() and any(output_dir.iterdir())
    if resuming:
        if not preflight_path.is_file() or json.loads(preflight_path.read_text()) != preflight:
            raise ValueError("incomplete run preflight mismatch")
        if not start_receipt_path.is_file():
            raise ValueError("incomplete run has no durable start receipt")
        start_receipt = json.loads(start_receipt_path.read_text())
        if (start_receipt.get("decision") != "PASS_SQCLI_START"
                or start_receipt.get("project_name") != project
                or start_receipt.get("preflight_sha256") != _sha256(preflight_path)):
            raise ValueError("incomplete run start receipt mismatch")

    listing = listing_fn(base_url)
    running = sorted(row.get("projectName") for row in listing
                     if row.get("runningStatus") not in (None, 0, 4, 50)
                     and not (resuming and row.get("projectName") == project))
    matches = [row for row in listing if row.get("projectName") == project]
    if running:
        raise RuntimeError(f"SQCLI already has running projects: {running}")
    if (len(matches) != 1 or matches[0].get("hasUnresolvedResources") is not False
            or (not resuming and matches[0].get("strategies") not in (None, 0))):
        raise RuntimeError("target SQCLI project is absent, unresolved, or not clean")
    if not resuming:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(preflight_path, preflight)
        response = start_fn(base_url, project)
        if not isinstance(response, dict) or response.get("success") is None:
            raise RuntimeError(f"SQCLI start failed: {response}")
        write_atomic(start_receipt_path, {
            "schema_version": 1, "decision": "PASS_SQCLI_START",
            "project_name": project, "preflight_path": str(preflight_path),
            "preflight_sha256": _sha256(preflight_path), "response": response,
            "paper_authorized": False, "live_authorized": False,
        })

    artifacts = projects_root.resolve() / project / "databanks"
    status_path = output_dir / "watchdog_status.json"
    journal_path = output_dir / "watchdog_journal.jsonl"
    final = monitor_fn(
        base_url=base_url, project=project, limits=load_limits(manifest_path),
        status_file=status_path, journal_file=journal_path,
        disk_path=disk_path, artifacts=artifacts, interval=interval,
        allow_control=True, snapshot_fn=gui_snapshot,
        call_fn=gui_project_action_from_cli,
        final_stats_fn=partial(docker_project_final_stats, container),
        started_project=True,
    )
    exact = final.get("attempt_counter_source") == "sq_project_final_log"
    within_budget = (isinstance(final.get("generated"), int)
                     and final["generated"] <= manifest["attempt_budget"])
    decision = ("PASS_SUPERVISED_SQ_RUN" if exact and within_budget
                else "FAIL_SUPERVISED_SQ_RUN")
    result = {
        "schema_version": 1, "decision": decision,
        "hypothesis_id": hypothesis_id, "project_name": project,
        "import_receipt_path": str(receipt_path),
        "import_receipt_sha256": _sha256(receipt_path),
        "project_source_cfx_path": str(Path(source["project_cfx_path"]).resolve()),
        "project_source_cfx_sha256": source["project_cfx_sha256"],
        "sq_imported_cfx_path": str(imported_cfx),
        "sq_imported_cfx_sha256": _sha256(imported_cfx),
        "project_manifest_path": str(manifest_path),
        "project_manifest_sha256": _sha256(manifest_path),
        "preflight_path": str(preflight_path), "preflight_sha256": _sha256(preflight_path),
        "start_receipt_path": str(start_receipt_path),
        "start_receipt_sha256": _sha256(start_receipt_path),
        "watchdog_status_path": str(status_path),
        "watchdog_status_sha256": _sha256(status_path),
        "watchdog_journal_path": str(journal_path),
        "watchdog_journal_sha256": _sha256(journal_path),
        "generated": final.get("generated"), "accepted": final.get("in_databank"),
        "hard_attempt_budget": manifest["attempt_budget"],
        "attempt_stop_guard": manifest["attempt_stop_guard"],
        "attempt_control_threshold": manifest["attempt_budget"] - manifest["attempt_stop_guard"],
        "exact_final_counters": exact, "within_hard_attempt_budget": within_budget,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_receipt_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-receipt", required=True, type=Path)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--disk-path", type=Path, default=Path("/mnt/volume-SQ"))
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    result = supervised_run(
        import_receipt_path=args.import_receipt, hypothesis_id=args.hypothesis,
        output_dir=args.output_dir, base_url=args.base_url, container=args.container,
        projects_root=args.projects_root, disk_path=args.disk_path, interval=args.interval)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
