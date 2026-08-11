#!/usr/bin/env python3
"""Import a verified CFX batch into SQCLI without starting any project."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sq_project_contract import verify_genetic_project
from lab.sq_bridge.sqcli_transport import (
    CONTAINER_NAME, SAFE_PROJECT_NAME, gui_open_project, list_projects,
)
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha256(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def import_batch(*, batch_path: Path, output_dir: Path,
                 base_url: str = "http://127.0.0.1:8080",
                 container: str = "sqcli-docker",
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    if not CONTAINER_NAME.fullmatch(container):
        raise ValueError("invalid SQCLI container name")
    batch_path = batch_path.resolve()
    batch = json.loads(batch_path.read_text())
    projects = batch.get("projects")
    selected = batch.get("selected_hypothesis_ids")
    if (batch.get("decision") != "PASS_CFX_BATCH_READY"
            or batch.get("sqcli_started") is not False
            or not isinstance(projects, dict) or not projects
            or not isinstance(selected, list) or sorted(projects) != sorted(selected)):
        raise ValueError("CFX batch does not authorize import")

    prepared = {}
    for hypothesis_id in sorted(projects):
        row = projects[hypothesis_id]
        if not isinstance(row, dict):
            raise ValueError(f"invalid project row: {hypothesis_id}")
        cfx = _file(row.get("project_cfx_path"), row.get("project_cfx_sha256"),
                    f"{hypothesis_id} CFX")
        manifest_path = _file(
            row.get("project_manifest_path"), row.get("project_manifest_sha256"),
            f"{hypothesis_id} manifest")
        manifest = json.loads(manifest_path.read_text())
        project_name = row.get("project_name")
        if (not isinstance(project_name, str) or not SAFE_PROJECT_NAME.fullmatch(project_name)
                or manifest.get("project_name") != project_name
                or verify_genetic_project(cfx, manifest) != row.get("sq_genetic_shape")):
            raise ValueError(f"{hypothesis_id} project contract mismatch")
        prepared[hypothesis_id] = (row, cfx, manifest)

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_sha256 = _sha256(batch_path)
    checkpoint_path = output_dir / "import_checkpoint.json"
    final_path = output_dir / "sqcli_import_receipt.json"
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text())
        if (checkpoint.get("schema_version") != 1
                or checkpoint.get("batch_path") != str(batch_path)
                or checkpoint.get("batch_sha256") != batch_sha256
                or not isinstance(checkpoint.get("projects"), dict)):
            raise ValueError("import checkpoint does not match frozen batch")
    else:
        unexpected = [path.name for path in output_dir.iterdir()]
        if unexpected:
            raise ValueError(f"import output has no checkpoint: {sorted(unexpected)}")
        checkpoint = {
            "schema_version": 1, "batch_path": str(batch_path),
            "batch_sha256": batch_sha256, "projects": {},
            "sqcli_started": False,
        }
        write_atomic(checkpoint_path, checkpoint)

    listing = {row.get("projectName"): row for row in list_projects(base_url)}
    if final_path.is_file():
        result = json.loads(final_path.read_text())
        if (result.get("decision") != "PASS_SQCLI_IMPORT"
                or result.get("batch_sha256") != batch_sha256
                or result.get("checkpoint_path") != str(checkpoint_path)
                or result.get("checkpoint_sha256") != _sha256(checkpoint_path)
                or set(result.get("projects") or {}) != set(prepared)):
            raise ValueError("completed import receipt does not match frozen batch")
        for hypothesis_id, imported_row in result["projects"].items():
            row, _, manifest = prepared[hypothesis_id]
            imported_cfx = _file(
                imported_row.get("sq_imported_cfx_path"),
                imported_row.get("sq_imported_cfx_sha256"),
                f"{hypothesis_id} completed imported CFX")
            current = listing.get(row["project_name"])
            if (verify_genetic_project(imported_cfx, manifest) != row["sq_genetic_shape"]
                    or current is None
                    or current.get("hasUnresolvedResources") is not False):
                raise RuntimeError(f"completed SQCLI import no longer verifies: {hypothesis_id}")
        return result

    imported = {}
    for hypothesis_id in sorted(prepared):
        row, cfx, manifest = prepared[hypothesis_id]
        project_name = row["project_name"]
        checkpoint_row = checkpoint["projects"].get(hypothesis_id)
        if checkpoint_row is not None and (
                not isinstance(checkpoint_row, dict)
                or checkpoint_row.get("project_name") != project_name
                or checkpoint_row.get("source_cfx_sha256") != row["project_cfx_sha256"]
                or checkpoint_row.get("state") not in {"IMPORT_INTENT", "VERIFIED"}):
            raise ValueError(f"invalid import checkpoint row: {hypothesis_id}")
        current = listing.get(project_name)
        if checkpoint_row is None:
            if current is not None:
                raise ValueError(f"SQCLI project collision: ['{project_name}']")
            checkpoint_row = {
                "state": "IMPORT_INTENT", "project_name": project_name,
                "source_cfx_sha256": row["project_cfx_sha256"],
            }
            checkpoint["projects"][hypothesis_id] = checkpoint_row
            write_atomic(checkpoint_path, checkpoint)
        elif checkpoint_row["state"] == "VERIFIED" and current is None:
            raise RuntimeError(f"verified imported project disappeared: {project_name}")

        if current is None:
            container_temp = f"/tmp/alquimia-import-{_sha256(cfx)[:16]}.cfx"
            copied = runner(
                ["docker", "cp", str(cfx), f"{container}:{container_temp}"],
                capture_output=True, text=True, timeout=30, check=False)
            if copied.returncode != 0:
                raise RuntimeError(f"cannot stage CFX for {project_name}")
            try:
                response = gui_open_project(base_url, container_temp)
            finally:
                runner(["docker", "exec", container, "rm", "--", container_temp],
                       capture_output=True, text=True, timeout=15, check=False)
            if response.get("projectName") != project_name:
                raise RuntimeError(f"SQCLI imported unexpected project: {response}")
        destination = output_dir / hypothesis_id / "sq_imported_project.cfx"
        destination.parent.mkdir(parents=True, exist_ok=True)
        inside = f"/home/squser/SQ/user/projects/{project_name}/project.cfx"
        exported = runner(
            ["docker", "cp", f"{container}:{inside}", str(destination)],
            capture_output=True, text=True, timeout=30, check=False)
        if exported.returncode != 0 or not destination.is_file():
            raise RuntimeError(f"cannot verify imported CFX for {project_name}")
        shape = verify_genetic_project(destination, manifest)
        if shape != row["sq_genetic_shape"]:
            raise RuntimeError(f"SQCLI changed scientific settings for {project_name}")
        imported[hypothesis_id] = {
            "project_name": project_name,
            "source_cfx_sha256": row["project_cfx_sha256"],
            "sq_imported_cfx_path": str(destination),
            "sq_imported_cfx_sha256": _sha256(destination),
            "sq_genetic_shape": shape,
            "has_unresolved_resources": False,
        }
        checkpoint["projects"][hypothesis_id] = {
            "state": "VERIFIED", "project_name": project_name,
            "source_cfx_sha256": row["project_cfx_sha256"],
            "sq_imported_cfx_path": str(destination),
            "sq_imported_cfx_sha256": _sha256(destination),
            "sq_genetic_shape": shape,
        }
        write_atomic(checkpoint_path, checkpoint)

    listing = {row.get("projectName"): row for row in list_projects(base_url)}
    for row in imported.values():
        current = listing.get(row["project_name"])
        if current is None or current.get("hasUnresolvedResources") is not False:
            raise RuntimeError(f"SQCLI imported project is unresolved: {row['project_name']}")
    result = {
        "schema_version": 1, "decision": "PASS_SQCLI_IMPORT",
        "batch_path": str(batch_path), "batch_sha256": batch_sha256,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "container": container, "projects": imported,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    args = parser.parse_args()
    result = import_batch(
        batch_path=args.batch, output_dir=args.output_dir,
        base_url=args.base_url, container=args.container)
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"]),
                      "sqcli_started": result["sqcli_started"]}, indent=2))


if __name__ == "__main__":
    main()
