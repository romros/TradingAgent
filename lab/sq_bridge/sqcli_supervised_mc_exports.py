#!/usr/bin/env python3
"""Export every native SQ Monte Carlo run with durable, resumable receipts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sqcli_transport import docker_exec_http_call
from lab.sq_bridge.sqx_monte_carlo_materialize import verify_manifest


REQUIRED_COLUMNS = {"Ticket", "Type", "Open time", "Open price", "Close time",
                    "Close price", "Size", "Profit/Loss", "MAE ($)"}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _container_path(path: Path, host_root: Path, container_root: str) -> str:
    try:
        relative = path.resolve().relative_to(host_root.resolve())
    except ValueError as exc:
        raise ValueError("MC_EXPORT_PATH_OUTSIDE_SQ_PROJECTS_ROOT") from exc
    if not container_root.startswith("/") or "\n" in container_root:
        raise ValueError("MC_EXPORT_CONTAINER_ROOT_INVALID")
    return f"{container_root.rstrip('/')}/{relative.as_posix()}"


def _verify_csv(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("MC_EXPORT_CSV_MISSING")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if REQUIRED_COLUMNS - set(reader.fieldnames or ()):
            raise ValueError("MC_EXPORT_CSV_COLUMNS_INVALID")
        count = sum(1 for _ in reader)
    return {"orders_csv_sha256": _sha(path), "trade_count": count,
            "orders_csv_size": path.stat().st_size}


def verify_export_receipt(path: Path) -> dict:
    result = json.loads(path.read_text())
    materialization = Path(result.get("materialization_manifest_path", ""))
    if (result.get("decision") != "PASS_SUPERVISED_MC_EXPORTS"
            or not materialization.is_file()
            or result.get("materialization_manifest_sha256") != _sha(materialization)):
        raise ValueError("MC_EXPORT_RECEIPT_INVALID")
    source = verify_manifest(materialization)
    rows = result.get("runs")
    if not isinstance(rows, list) or len(rows) != len(source["runs"]):
        raise ValueError("MC_EXPORT_RECEIPT_RUN_COUNT_INVALID")
    for expected, row in zip(source["runs"], rows, strict=True):
        csv_path = Path(row.get("orders_csv_path", ""))
        observed = _verify_csv(csv_path)
        if (row.get("run_id") != expected["run_id"]
                or row.get("materialized_sqx_sha256")
                    != expected["materialized_sqx_sha256"]
                or any(row.get(key) != value for key, value in observed.items())):
            raise ValueError("MC_EXPORT_RECEIPT_RUN_LINEAGE_INVALID")
    return result


def export_all(*, materialization_manifest: Path, output_dir: Path,
               host_projects_root: Path,
               container_projects_root: str = "/home/squser/SQ/user/projects",
               container: str = "sqcli-docker",
               export_fn: Callable[[str], str] | None = None,
               progress_hook: Callable[[dict], None] | None = None) -> dict:
    source = verify_manifest(materialization_manifest)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = output_dir / "checkpoints"
    checkpoints.mkdir(exist_ok=True)
    final_path = output_dir / "supervised-mc-exports.receipt.json"
    if final_path.is_file():
        return verify_export_receipt(final_path)
    exporter = export_fn or (lambda command: docker_exec_http_call(container, command))
    completed = []
    total = len(source["runs"])
    for index, run in enumerate(source["runs"]):
        run_id = run["run_id"]
        if not SAFE_COMPONENT.fullmatch(run_id):
            raise ValueError("MC_EXPORT_RUN_ID_INVALID")
        sqx = Path(run["materialized_sqx_path"])
        checkpoint = checkpoints / f"{run_id}.json"
        csv_path = output_dir / f"{run_id}.orders.csv"
        if checkpoint.is_file():
            row = json.loads(checkpoint.read_text())
            observed = _verify_csv(csv_path)
            if (row.get("run_id") != run_id
                    or row.get("materialized_sqx_sha256")
                        != run["materialized_sqx_sha256"]
                    or any(row.get(key) != value for key, value in observed.items())):
                raise ValueError("MC_EXPORT_CHECKPOINT_INVALID")
            completed.append(row)
            if progress_hook:
                progress_hook({"event": "reused", "run_id": run_id,
                               "completed": index + 1, "total": total})
            continue
        sqx_container = _container_path(
            sqx, host_projects_root, container_projects_root)
        output_prefix = csv_path.with_suffix("")
        output_container = _container_path(
            output_prefix, host_projects_root, container_projects_root)
        command = (f"-tools action=orderstocsv file={sqx_container} "
                   f"output={output_container} usecomma=true data=main")
        response = "recovered_existing_verified_csv"
        if not csv_path.is_file():
            response = exporter(command)
        observed = _verify_csv(csv_path)
        row = {
            "run_id": run_id,
            "materialized_sqx_path": str(sqx.resolve()),
            "materialized_sqx_sha256": run["materialized_sqx_sha256"],
            "orders_csv_path": str(csv_path),
            **observed,
            "command": command,
            "response": response,
        }
        _write_atomic(checkpoint, row)
        completed.append(row)
        if progress_hook:
            progress_hook({"event": "exported", "run_id": run_id,
                           "completed": index + 1, "total": total})
    result = {
        "schema_version": 1,
        "decision": "PASS_SUPERVISED_MC_EXPORTS",
        "materialization_manifest_path": str(materialization_manifest.resolve()),
        "materialization_manifest_sha256": _sha(materialization_manifest),
        "simulation_count": total,
        "completed_count": len(completed),
        "zero_trade_run_count": sum(row["trade_count"] == 0 for row in completed),
        "runs": completed,
        "paper_authorized": False,
        "live_authorized": False,
    }
    _write_atomic(final_path, result)
    return verify_export_receipt(final_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materialization-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--host-projects-root", required=True, type=Path)
    parser.add_argument("--container-projects-root",
                        default="/home/squser/SQ/user/projects")
    parser.add_argument("--container", default="sqcli-docker")
    args = parser.parse_args()
    result = export_all(
        materialization_manifest=args.materialization_manifest,
        output_dir=args.output_dir, host_projects_root=args.host_projects_root,
        container_projects_root=args.container_projects_root,
        container=args.container,
        progress_hook=lambda row: print(json.dumps(row), flush=True))
    print(json.dumps({"decision": result["decision"],
                      "completed_count": result["completed_count"],
                      "zero_trade_run_count": result["zero_trade_run_count"]}, indent=2))


if __name__ == "__main__":
    main()
