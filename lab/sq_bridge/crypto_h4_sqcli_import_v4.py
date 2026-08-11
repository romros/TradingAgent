#!/usr/bin/env python3
"""Import a verified crypto H4 CFX batch into idle SQCLI without starting it."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.crypto_h4_cfx_v4 import verify_cfx
from lab.sq_bridge.crypto_h4_project_batch_v4 import verify_project_row
from lab.sq_bridge.sqcli_transport import (
    CONTAINER_NAME, SAFE_PROJECT_NAME, gui_open_project, list_projects_with_status,
)
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


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


def import_batch(*, batch_path: Path, output_dir: Path,
                 base_url: str = "http://127.0.0.1:8080",
                 container: str = "sqcli-docker",
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 list_fn: Callable[..., list[dict]] = list_projects_with_status,
                 open_fn: Callable[..., dict] = gui_open_project) -> dict[str, Any]:
    if not CONTAINER_NAME.fullmatch(container):
        raise ValueError("invalid SQCLI container name")
    batch_path = batch_path.resolve()
    batch = _load(batch_path)
    selected, projects = batch.get("selected_candidate_ids"), batch.get("projects")
    if (batch.get("decision") != "PASS_CRYPTO_CFX_BATCH_READY"
            or batch.get("translation_scope") != "sq_proposal_generation_only"
            or batch.get("python_parity_required") is not True
            or batch.get("strategy_promotion_authorized") is not False
            or batch.get("sqcli_started") is not False
            or not isinstance(selected, list) or not selected
            or not isinstance(projects, dict) or selected != list(projects)
            or set(selected) != set(projects)):
        raise ValueError("crypto CFX batch does not authorize import")
    prepared = {}
    frozen_inputs = batch.get("inputs")
    if not isinstance(frozen_inputs, dict):
        raise ValueError("crypto CFX batch inputs missing")
    for candidate_id in selected:
        row = verify_project_row(candidate_id, projects[candidate_id], frozen_inputs)
        manifest_path = _verified_file(row.get("manifest_path"),
                                       row.get("manifest_sha256"),
                                       f"{candidate_id} manifest")
        cfx_path = _verified_file(row.get("cfx_path"), row.get("cfx_sha256"),
                                  f"{candidate_id} CFX")
        manifest = _load(manifest_path)
        project_name = row.get("project_name")
        if (not isinstance(project_name, str)
                or not SAFE_PROJECT_NAME.fullmatch(project_name)
                or manifest.get("project_name") != project_name):
            raise ValueError(f"invalid crypto SQ project identity: {candidate_id}")
        prepared[candidate_id] = (row, cfx_path, manifest)

    output_dir = output_dir.resolve()
    final_path = output_dir / "crypto_h4_sqcli_import_receipt.json"
    checkpoint_path = output_dir / "crypto_h4_sqcli_import_checkpoint.json"
    batch_sha = _sha(batch_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = {"schema_version": 1, "batch_path": str(batch_path),
                "batch_sha256": batch_sha, "container": container,
                "selected_candidate_ids": selected, "projects": {},
                "sqcli_started": False}
    if checkpoint_path.is_file():
        checkpoint = _load(checkpoint_path)
        expected = {**contract, "projects": checkpoint.get("projects")}
        if not isinstance(checkpoint.get("projects"), dict) or checkpoint != expected:
            raise ValueError("crypto SQCLI import checkpoint changed")
    else:
        unexpected = sorted(path.name for path in output_dir.iterdir())
        if unexpected:
            raise ValueError(f"crypto SQCLI import output has no checkpoint: {unexpected}")
        checkpoint = contract
        write_atomic(checkpoint_path, checkpoint)

    listing = {row.get("projectName"): row for row in list_fn(base_url)}
    running = sorted(name for name, row in listing.items()
                     if isinstance(name, str)
                     and row.get("runningStatus") not in TERMINAL_SQ_STATUSES)
    if running:
        raise RuntimeError(f"refusing crypto import while SQCLI projects run: {running}")
    if final_path.is_file():
        result = _load(final_path)
        if (result.get("decision") != "PASS_CRYPTO_SQCLI_IMPORT"
                or result.get("batch_sha256") != batch_sha
                or result.get("batch_path") != str(batch_path)
                or result.get("checkpoint_path") != str(checkpoint_path)
                or result.get("checkpoint_sha256") != _sha(checkpoint_path)
                or result.get("container") != container
                or result.get("selected_candidate_ids") != selected
                or result.get("translation_scope") != "sq_proposal_generation_only"
                or result.get("python_parity_required") is not True
                or result.get("strategy_promotion_authorized") is not False
                or result.get("sqcli_started") is not False
                or set(result.get("projects") or {}) != set(selected)):
            raise ValueError("completed crypto SQCLI import changed")
        for candidate_id, imported in result["projects"].items():
            _, _, manifest = prepared[candidate_id]
            imported_cfx = _verified_file(
                imported.get("imported_cfx_path"), imported.get("imported_cfx_sha256"),
                f"{candidate_id} imported CFX")
            current = listing.get(imported.get("project_name"))
            if (verify_cfx(imported_cfx, manifest, require_archive_hash=False)["valid"]
                    is not True or current is None
                    or current.get("hasUnresolvedResources") is not False
                    or current.get("runningStatus") != 0):
                raise RuntimeError(f"completed crypto import no longer verifies: {candidate_id}")
        return result

    imported_rows = {}
    for candidate_id in selected:
        row, cfx_path, manifest = prepared[candidate_id]
        project_name = row["project_name"]
        saved = checkpoint["projects"].get(candidate_id)
        if saved is None:
            if project_name in listing:
                raise ValueError(f"SQCLI crypto project collision: {project_name}")
            saved = {"state": "IMPORT_INTENT", "project_name": project_name,
                     "source_cfx_sha256": row["cfx_sha256"]}
            checkpoint["projects"][candidate_id] = saved
            write_atomic(checkpoint_path, checkpoint)
        elif (not isinstance(saved, dict) or saved.get("project_name") != project_name
              or saved.get("source_cfx_sha256") != row["cfx_sha256"]
              or saved.get("state") not in {"IMPORT_INTENT", "VERIFIED"}):
            raise ValueError(f"invalid crypto import checkpoint: {candidate_id}")
        current = listing.get(project_name)
        if saved["state"] == "VERIFIED" and current is None:
            raise RuntimeError(f"verified crypto SQ project disappeared: {project_name}")
        if current is None:
            temporary = f"/tmp/alquimia-crypto-{row['cfx_sha256'][:16]}.cfx"
            copied = runner(["docker", "cp", str(cfx_path), f"{container}:{temporary}"],
                            capture_output=True, text=True, timeout=30, check=False)
            if copied.returncode != 0:
                raise RuntimeError(f"cannot stage crypto CFX: {candidate_id}")
            try:
                response = open_fn(base_url, temporary)
            finally:
                runner(["docker", "exec", container, "rm", "--", temporary],
                       capture_output=True, text=True, timeout=15, check=False)
            if response.get("projectName") != project_name:
                raise RuntimeError(f"SQCLI imported unexpected crypto project: {response}")
        destination = output_dir / candidate_id / "sq_imported_project.cfx"
        destination.parent.mkdir(parents=True, exist_ok=True)
        inside = f"/home/squser/SQ/user/projects/{project_name}/project.cfx"
        exported = runner(["docker", "cp", f"{container}:{inside}", str(destination)],
                          capture_output=True, text=True, timeout=30, check=False)
        if exported.returncode != 0 or not destination.is_file():
            raise RuntimeError(f"cannot export imported crypto CFX: {candidate_id}")
        verification = verify_cfx(destination, manifest, require_archive_hash=False)
        refreshed = {item.get("projectName"): item for item in list_fn(base_url)}
        current = refreshed.get(project_name)
        running_now = sorted(name for name, item in refreshed.items()
                             if isinstance(name, str)
                             and item.get("runningStatus") not in TERMINAL_SQ_STATUSES)
        if (running_now or current is None
                or current.get("hasUnresolvedResources") is not False):
            raise RuntimeError(
                f"SQCLI crypto project unresolved after import: {project_name}")
        imported_row = {"candidate_id": candidate_id, "project_name": project_name,
                        "source_cfx_sha256": row["cfx_sha256"],
                        "imported_cfx_path": str(destination),
                        "imported_cfx_sha256": _sha(destination),
                        "genetic_shape": list(verification["shape"]),
                        "has_unresolved_resources": False,
                        "sqcli_started": False}
        imported_rows[candidate_id] = imported_row
        checkpoint["projects"][candidate_id] = {
            "state": "VERIFIED", "project_name": project_name,
            "source_cfx_sha256": row["cfx_sha256"], "project": imported_row}
        write_atomic(checkpoint_path, checkpoint)
        listing[project_name] = {"projectName": project_name, "runningStatus": 0,
                                 "hasUnresolvedResources": False}

    authoritative = {row.get("projectName"): row for row in list_fn(base_url)}
    for imported in imported_rows.values():
        current = authoritative.get(imported["project_name"])
        if (current is None or current.get("hasUnresolvedResources") is not False
                or current.get("runningStatus") != 0):
            raise RuntimeError(f"SQCLI crypto project unresolved: {imported['project_name']}")
    result = {"schema_version": 1, "stage": "crypto_h4_sqcli_import",
              "decision": "PASS_CRYPTO_SQCLI_IMPORT",
              "batch_path": str(batch_path), "batch_sha256": batch_sha,
              "selected_candidate_ids": selected,
              "checkpoint_path": str(checkpoint_path),
              "checkpoint_sha256": _sha(checkpoint_path), "container": container,
              "projects": imported_rows, "sqcli_started": False,
              "translation_scope": "sq_proposal_generation_only",
              "python_parity_required": True,
              "strategy_promotion_authorized": False,
              "paper_authorized": False, "live_authorized": False,
              "performance_accessed": False}
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    args = parser.parse_args()
    result = import_batch(batch_path=args.batch, output_dir=args.output_dir,
                          base_url=args.base_url, container=args.container)
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"]),
                      "sqcli_started": result["sqcli_started"]}, indent=2))


if __name__ == "__main__":
    main()
