#!/usr/bin/env python3
"""Run one imported crypto H4 SQ project with exact, resumable evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.crypto_h4_cfx_v4 import verify_cfx
from lab.sq_bridge.crypto_h4_project_batch_v4 import verify_project_row
from lab.sq_bridge.sq_watchdog import gui_snapshot, load_limits, run_monitor, write_atomic
from lab.sq_bridge.sqcli_transport import (
    docker_project_final_stats,
    gui_project_action_from_cli,
    gui_start_project,
    list_projects_with_status,
)


TERMINAL_SQ_STATUSES = {0, 4, 50}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verified_file(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _completed(path: Path, candidate_id: str, project: str) -> dict[str, Any]:
    result = _load(path)
    if (result.get("decision") not in {
            "PASS_CRYPTO_H4_SUPERVISED_RUN", "FAIL_CRYPTO_H4_SUPERVISED_RUN"}
            or result.get("candidate_id") != candidate_id
            or result.get("project_name") != project):
        raise ValueError("completed crypto run identity mismatch")
    for label, path_key, hash_key in (
            ("preflight", "preflight_path", "preflight_sha256"),
            ("start receipt", "start_receipt_path", "start_receipt_sha256"),
            ("watchdog status", "watchdog_status_path", "watchdog_status_sha256"),
            ("watchdog journal", "watchdog_journal_path", "watchdog_journal_sha256"),
            ("SQ final log", "final_log_path", "final_log_sha256")):
        _verified_file(result.get(path_key), result.get(hash_key), label)
    return result


def supervised_run(
    *, import_receipt_path: Path, candidate_id: str, output_dir: Path,
    base_url: str = "http://127.0.0.1:8080", container: str = "sqcli-docker",
    projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
    disk_path: Path = Path("/mnt/volume-SQ"), interval: int = 5,
    listing_fn: Callable[..., list[dict]] = list_projects_with_status,
    start_fn: Callable[..., dict] = gui_start_project,
    monitor_fn: Callable[..., dict] = run_monitor,
) -> dict[str, Any]:
    """Start or resume exactly one crypto project and freeze its final SQ log."""
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate id missing")
    receipt_path = import_receipt_path.resolve()
    receipt = _load(receipt_path)
    selected, imported_projects = (receipt.get("selected_candidate_ids"),
                                   receipt.get("projects"))
    if (receipt.get("decision") != "PASS_CRYPTO_SQCLI_IMPORT"
            or receipt.get("sqcli_started") is not False
            or not isinstance(selected, list) or candidate_id not in selected
            or not isinstance(imported_projects, dict)
            or set(selected) != set(imported_projects)):
        raise ValueError("crypto import receipt does not authorize this run")
    checkpoint_path = _verified_file(
        receipt.get("checkpoint_path"), receipt.get("checkpoint_sha256"),
        "crypto import checkpoint")
    checkpoint = _load(checkpoint_path)
    batch_path = _verified_file(receipt.get("batch_path"), receipt.get("batch_sha256"),
                                "crypto source batch")
    batch = _load(batch_path)
    if (checkpoint.get("batch_sha256") != receipt.get("batch_sha256")
            or checkpoint.get("selected_candidate_ids") != selected
            or not isinstance(checkpoint.get("projects"), dict)
            or set(checkpoint["projects"]) != set(selected)):
        raise ValueError("crypto import checkpoint lineage mismatch")
    imported = imported_projects[candidate_id]
    saved = checkpoint["projects"][candidate_id]
    if (not isinstance(imported, dict) or not isinstance(saved, dict)
            or saved.get("state") != "VERIFIED" or saved.get("project") != imported):
        raise ValueError("crypto imported project is not durably verified")
    source_projects = batch.get("projects")
    frozen_inputs = batch.get("inputs")
    if not isinstance(source_projects, dict) or not isinstance(frozen_inputs, dict):
        raise ValueError("crypto source batch incomplete")
    source = verify_project_row(candidate_id, source_projects.get(candidate_id),
                                frozen_inputs)
    manifest_path = _verified_file(source.get("manifest_path"),
                                   source.get("manifest_sha256"), "project manifest")
    manifest = _load(manifest_path)
    imported_cfx = _verified_file(imported.get("imported_cfx_path"),
                                  imported.get("imported_cfx_sha256"),
                                  "SQ imported CFX")
    project = imported.get("project_name")
    if (project != source.get("project_name")
            or imported.get("source_cfx_sha256") != source.get("cfx_sha256")
            or imported.get("has_unresolved_resources") is not False
            or verify_cfx(imported_cfx, manifest,
                          require_archive_hash=False)["valid"] is not True):
        raise ValueError("crypto imported project contract mismatch")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise ValueError("monitor interval must be positive")

    output_dir = output_dir.resolve()
    preflight = {
        "schema_version": 1, "decision": "PASS_CRYPTO_H4_RUN_PREFLIGHT",
        "candidate_id": candidate_id, "project_name": project,
        "import_receipt_path": str(receipt_path),
        "import_receipt_sha256": _sha(receipt_path),
        "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
        "imported_cfx_path": str(imported_cfx),
        "imported_cfx_sha256": _sha(imported_cfx),
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    preflight_path = output_dir / "run_preflight.json"
    start_path = output_dir / "start_receipt.json"
    final_path = output_dir / "crypto_h4_supervised_run_receipt.json"
    if final_path.is_file():
        return _completed(final_path, candidate_id, str(project))
    resuming = output_dir.exists() and any(output_dir.iterdir())
    if resuming:
        if not preflight_path.is_file() or _load(preflight_path) != preflight:
            raise ValueError("incomplete crypto run preflight mismatch")
        if not start_path.is_file():
            raise ValueError("incomplete crypto run has no durable start receipt")
        start_receipt = _load(start_path)
        if (start_receipt.get("decision") != "PASS_CRYPTO_H4_SQCLI_START"
                or start_receipt.get("project_name") != project
                or start_receipt.get("preflight_sha256") != _sha(preflight_path)):
            raise ValueError("incomplete crypto start receipt mismatch")

    listing = listing_fn(base_url)
    active = sorted(row.get("projectName") for row in listing
                    if row.get("runningStatus") not in TERMINAL_SQ_STATUSES
                    and not (resuming and row.get("projectName") == project))
    matches = [row for row in listing if row.get("projectName") == project]
    if active:
        raise RuntimeError(f"SQCLI already has active projects: {active}")
    if (len(matches) != 1 or matches[0].get("hasUnresolvedResources") is not False
            or (not resuming and (matches[0].get("runningStatus") != 0
                                  or matches[0].get("strategies") not in (None, 0)))):
        raise RuntimeError("target crypto SQ project is absent, unresolved, or not clean")
    if not resuming:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(preflight_path, preflight)
        response = start_fn(base_url, str(project))
        if not isinstance(response, dict) or response.get("success") is None:
            raise RuntimeError(f"crypto SQCLI start failed: {response}")
        write_atomic(start_path, {
            "schema_version": 1, "decision": "PASS_CRYPTO_H4_SQCLI_START",
            "candidate_id": candidate_id, "project_name": project,
            "preflight_path": str(preflight_path),
            "preflight_sha256": _sha(preflight_path), "response": response,
            "paper_authorized": False, "live_authorized": False,
        })

    databank = projects_root.resolve() / str(project) / "databanks"
    status_path = output_dir / "watchdog_status.json"
    journal_path = output_dir / "watchdog_journal.jsonl"
    final = monitor_fn(
        base_url=base_url, project=str(project), limits=load_limits(manifest_path),
        status_file=status_path, journal_file=journal_path,
        disk_path=disk_path, artifacts=databank, interval=interval,
        allow_control=True, snapshot_fn=gui_snapshot,
        call_fn=gui_project_action_from_cli,
        final_stats_fn=partial(docker_project_final_stats, container),
        started_project=True,
    )
    final_log = _verified_file(final.get("sq_final_log_path"),
                               final.get("sq_final_log_sha256"), "SQ final log")
    exact = final.get("attempt_counter_source") == "sq_project_final_log"
    generated = final.get("generated")
    accepted = final.get("in_databank")
    within_budget = (isinstance(generated, int) and not isinstance(generated, bool)
                     and generated <= manifest["attempt_budget"])
    inventory = final.get("artifacts")
    inventory_exact = (isinstance(inventory, list)
                       and isinstance(accepted, int) and not isinstance(accepted, bool)
                       and len(inventory) == accepted)
    decision = ("PASS_CRYPTO_H4_SUPERVISED_RUN"
                if exact and within_budget and inventory_exact
                else "FAIL_CRYPTO_H4_SUPERVISED_RUN")
    result = {
        "schema_version": 1, "stage": "crypto_h4_sqcli_supervised_run",
        "decision": decision, "candidate_id": candidate_id,
        "project_name": project, "import_receipt_path": str(receipt_path),
        "import_receipt_sha256": _sha(receipt_path),
        "imported_cfx_path": str(imported_cfx),
        "imported_cfx_sha256": _sha(imported_cfx),
        "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
        "preflight_path": str(preflight_path), "preflight_sha256": _sha(preflight_path),
        "start_receipt_path": str(start_path), "start_receipt_sha256": _sha(start_path),
        "watchdog_status_path": str(status_path),
        "watchdog_status_sha256": _sha(status_path),
        "watchdog_journal_path": str(journal_path),
        "watchdog_journal_sha256": _sha(journal_path),
        "final_log_path": str(final_log), "final_log_sha256": _sha(final_log),
        "databank_dir": str(databank), "generated": generated, "accepted": accepted,
        "hard_attempt_budget": manifest["attempt_budget"],
        "attempt_stop_guard": manifest["attempt_stop_guard"],
        "attempt_control_threshold": (manifest["attempt_budget"]
                                      - manifest["attempt_stop_guard"]),
        "exact_final_counters": exact, "within_hard_attempt_budget": within_budget,
        "databank_inventory_exact": inventory_exact,
        "costs_accessed": False, "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "strategy_promotion_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-receipt", required=True, type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--disk-path", type=Path, default=Path("/mnt/volume-SQ"))
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    result = supervised_run(
        import_receipt_path=args.import_receipt, candidate_id=args.candidate,
        output_dir=args.output_dir, base_url=args.base_url, container=args.container,
        projects_root=args.projects_root, disk_path=args.disk_path,
        interval=args.interval)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
