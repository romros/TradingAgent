#!/usr/bin/env python3
"""Resumable SQ execution + observed generation artifact for one v4 hypothesis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sq_generation_artifact_v4 import build_artifact
from lab.sq_bridge.sqcli_supervised_run import supervised_run


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha256(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def run_stage(
    *, import_receipt_path: Path, hypothesis_id: str, campaign_id: str,
    methodology_path: Path, run_dir: Path, output_path: Path,
    projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
    disk_path: Path = Path("/mnt/volume-SQ"),
    base_url: str = "http://127.0.0.1:8080", container: str = "sqcli-docker",
    interval: int = 5,
    supervisor: Callable[..., dict] = supervised_run,
    builder: Callable[..., dict] = build_artifact,
) -> dict:
    """Run or resume SQ, then derive the stage decision only from frozen files."""
    run = supervisor(
        import_receipt_path=import_receipt_path, hypothesis_id=hypothesis_id,
        output_dir=run_dir, base_url=base_url, container=container,
        projects_root=projects_root, disk_path=disk_path, interval=interval)
    if run.get("decision") != "PASS_SUPERVISED_SQ_RUN":
        raise RuntimeError(f"supervised SQ run did not pass: {run.get('decision')}")
    receipt_path = import_receipt_path.resolve()
    receipt = json.loads(receipt_path.read_text())
    batch_path = _file(receipt.get("batch_path"), receipt.get("batch_sha256"), "batch")
    batch = json.loads(batch_path.read_text())
    source = (batch.get("projects") or {}).get(hypothesis_id)
    imported = (receipt.get("projects") or {}).get(hypothesis_id)
    if not isinstance(source, dict) or not isinstance(imported, dict):
        raise ValueError("hypothesis absent from import lineage")
    project_cfx = _file(
        source.get("project_cfx_path"), source.get("project_cfx_sha256"), "source CFX")
    project_manifest = _file(
        source.get("project_manifest_path"), source.get("project_manifest_sha256"),
        "project manifest")
    project_name = source.get("project_name")
    if project_name != imported.get("project_name") or project_name != run.get("project_name"):
        raise ValueError("project identity changed between batch/import/run")
    watchdog_status = _file(
        run.get("watchdog_status_path"), run.get("watchdog_status_sha256"),
        "watchdog status")
    databank = projects_root.resolve() / str(project_name) / "databanks"
    artifact = builder(
        campaign_id=campaign_id, source_hypothesis_ids=[hypothesis_id],
        databank_dir=databank, watchdog_status_path=watchdog_status,
        project_cfx=project_cfx, project_manifest_path=project_manifest,
        methodology_path=methodology_path, output_path=output_path)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise RuntimeError("generation artifact returned an invalid decision")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-receipt", required=True, type=Path)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--methodology", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--disk-path", type=Path, default=Path("/mnt/volume-SQ"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    artifact = run_stage(
        import_receipt_path=args.import_receipt, hypothesis_id=args.hypothesis,
        campaign_id=args.campaign_id, methodology_path=args.methodology,
        run_dir=args.run_dir, output_path=args.output,
        projects_root=args.projects_root, disk_path=args.disk_path,
        base_url=args.base_url, container=args.container, interval=args.interval)
    print(json.dumps({"decision": artifact["decision"],
                      "candidate_ids": artifact["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
