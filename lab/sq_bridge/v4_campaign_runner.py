#!/usr/bin/env python3
"""Checkpointed, fail-closed executor for Alquimia v4 stage commands."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.sq_bridge.evidence_chain import append_receipt, new_chain, verify
from lab.sq_bridge.methodology import validate as validate_methodology


OUTPUT_TAIL_BYTES = 16 * 1024
SECRET_PATTERN = re.compile(
    r"(?i)(license(?:[_ -]?code)?|api[_ -]?key|access[_ -]?token|token|secret|"
    r"private[_ -]?key)(\s*[:=]\s*)([^\s,;]+)"
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact(value: str) -> str:
    """Hide conventional secret assignments without claiming perfect DLP."""
    return SECRET_PATTERN.sub(r"\1\2***", value)


def output_summary(handle: Any) -> dict[str, Any]:
    """Hash a seekable binary stream and retain only its bounded diagnostic tail."""
    handle.flush()
    handle.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := handle.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    handle.seek(max(0, size - OUTPUT_TAIL_BYTES))
    tail = handle.read(OUTPUT_TAIL_BYTES).decode("utf-8", errors="replace")
    return {
        "bytes": size,
        "sha256": digest.hexdigest(),
        "truncated": size > OUTPUT_TAIL_BYTES,
        "redacted_tail": redact(tail),
    }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def load_contract(manifest_path: Path) -> tuple[dict, Path, dict, Path]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("campaign runner manifest must use schema_version=1")
    required = ("campaign_id", "hypothesis_id", "market", "methodology", "state_dir", "stages")
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError(f"manifest missing: {', '.join(missing)}")
    methodology_path = resolve(manifest_path.parent, manifest["methodology"])
    methodology = json.loads(methodology_path.read_text())
    errors = validate_methodology(methodology)
    if errors or methodology.get("schema_version") != 4:
        raise ValueError(f"runner requires valid methodology v4: {errors}")
    if set(manifest["stages"]) != set(methodology["stages"]):
        raise ValueError("manifest must define every v4 stage exactly once")
    for stage in methodology["stages"]:
        spec = manifest["stages"][stage]
        command = spec.get("command")
        if not isinstance(command, list) or not command or any(
                not isinstance(item, str) or not item for item in command):
            raise ValueError(f"{stage}: command must be a non-empty string array")
        timeout = spec.get("timeout_seconds", 3600)
        if not isinstance(timeout, int) or timeout < 1:
            raise ValueError(f"{stage}: timeout_seconds must be a positive integer")
    return manifest, methodology_path, methodology, resolve(manifest_path.parent, manifest["state_dir"])


def chain_path(state_dir: Path) -> Path:
    return state_dir / "chain.json"


def initialize(manifest: dict, methodology_path: Path, state_dir: Path) -> dict:
    path = chain_path(state_dir)
    if path.exists():
        return json.loads(path.read_text())
    chain = new_chain(methodology_path, manifest["campaign_id"], manifest["hypothesis_id"],
                      manifest["market"], "alquimia_native")
    atomic_json(path, chain)
    return chain


def freeze_manifest(manifest_path: Path, state_dir: Path) -> tuple[bool, str]:
    digest = hashlib.sha256(manifest_path.resolve().read_bytes()).hexdigest()
    contract_path = state_dir / "runner_contract.json"
    if contract_path.exists():
        stored = json.loads(contract_path.read_text()).get("manifest_sha256")
        return stored == digest, digest
    atomic_json(contract_path, {"schema_version": 1, "manifest": str(manifest_path.resolve()),
                                "manifest_sha256": digest, "frozen_at": now()})
    return True, digest


def status(manifest_path: Path) -> dict[str, Any]:
    manifest, methodology_path, methodology, state_dir = load_contract(manifest_path)
    path = chain_path(state_dir)
    contract_path = state_dir / "runner_contract.json"
    if contract_path.exists():
        current = hashlib.sha256(manifest_path.resolve().read_bytes()).hexdigest()
        frozen = json.loads(contract_path.read_text()).get("manifest_sha256")
        if current != frozen:
            return {"status": "MANIFEST_CHANGED", "campaign_id": manifest["campaign_id"],
                    "state_dir": str(state_dir), "frozen_manifest_sha256": frozen,
                    "current_manifest_sha256": current}
    if not path.exists():
        return {"status": "NOT_STARTED", "campaign_id": manifest["campaign_id"],
                "next_stage": methodology["stages"][0], "state_dir": str(state_dir)}
    result = verify(json.loads(path.read_text()), methodology_path)
    return {"status": "INVALID" if not result["valid"] else (
                "TERMINAL" if result["terminal"] else (
                    "COMPLETE" if result["next_stage"] is None else "READY")),
            "campaign_id": manifest["campaign_id"], "state_dir": str(state_dir), **result}


def render_command(command: list[str], *, stage: str, artifact: Path,
                   state_dir: Path, manifest_path: Path) -> list[str]:
    values = {"stage": stage, "artifact": str(artifact), "state_dir": str(state_dir),
              "manifest": str(manifest_path.resolve())}
    try:
        return [item.format(**values) for item in command]
    except KeyError as exc:
        raise ValueError(f"unsupported command placeholder: {exc}") from exc


def run_next(manifest_path: Path) -> dict[str, Any]:
    manifest, methodology_path, methodology, state_dir = load_contract(manifest_path)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / ".runner.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("campaign runner is already active") from exc
        manifest_matches, current_manifest_sha256 = freeze_manifest(manifest_path, state_dir)
        if not manifest_matches:
            return {"status": "MANIFEST_CHANGED", "chain_unchanged": True,
                    "current_manifest_sha256": current_manifest_sha256}
        chain = initialize(manifest, methodology_path, state_dir)
        before = verify(chain, methodology_path)
        if not before["valid"]:
            return {"status": "INVALID_CHAIN", **before}
        if before["terminal"] or before["next_stage"] is None:
            return {"status": "NO_WORK", **before}
        stage = before["next_stage"]
        spec = manifest["stages"][stage]
        artifacts = state_dir / "artifacts"
        logs = state_dir / "logs"
        artifacts.mkdir(exist_ok=True)
        logs.mkdir(exist_ok=True)
        final_artifact = artifacts / f"{len(chain['receipts']) + 1:02d}_{stage}.json"
        pending = artifacts / f".{final_artifact.name}.pending"
        pending.unlink(missing_ok=True)
        command = render_command(spec["command"], stage=stage, artifact=pending,
                                 state_dir=state_dir, manifest_path=manifest_path)
        started = now()
        with tempfile.TemporaryFile(mode="w+b") as stdout_handle, \
                tempfile.TemporaryFile(mode="w+b") as stderr_handle:
            try:
                completed = subprocess.run(
                    command,
                    cwd=resolve(manifest_path.resolve().parent, spec.get("cwd", ".")),
                    stdout=stdout_handle, stderr=stderr_handle,
                    timeout=spec.get("timeout_seconds", 3600), check=False,
                    env={**os.environ, "ALQUIMIA_STAGE": stage,
                         "ALQUIMIA_STAGE_ARTIFACT": str(pending)},
                )
                timed_out = False
            except subprocess.TimeoutExpired:
                completed, timed_out = None, True
            log = {
                "schema_version": 1, "stage": stage, "started_at": started,
                "finished_at": now(), "command": [redact(item) for item in command],
                "timed_out": timed_out,
                "returncode": None if timed_out else completed.returncode,
                "stdout_summary": output_summary(stdout_handle),
                "stderr_summary": output_summary(stderr_handle),
            }
        atomic_json(logs / f"{len(chain['receipts']) + 1:02d}_{stage}.json", log)
        if timed_out or completed.returncode != 0:
            pending.unlink(missing_ok=True)
            return {"status": "STAGE_TIMEOUT" if timed_out else "STAGE_COMMAND_FAILED",
                    "stage": stage, "chain_unchanged": True,
                    "returncode": None if timed_out else completed.returncode}
        if not pending.is_file():
            return {"status": "STAGE_ARTIFACT_MISSING", "stage": stage,
                    "chain_unchanged": True}
        try:
            artifact = json.loads(pending.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            pending.unlink(missing_ok=True)
            return {"status": "STAGE_ARTIFACT_INVALID_JSON", "stage": stage,
                    "chain_unchanged": True, "error": str(exc)}
        decision = artifact.get("decision")
        candidate_ids = artifact.get("candidate_ids")
        if decision not in {"PASS", "REJECT", "BLOCK"} or not isinstance(candidate_ids, list):
            pending.unlink(missing_ok=True)
            return {"status": "STAGE_ARTIFACT_INVALID_CONTRACT", "stage": stage,
                    "chain_unchanged": True}
        pending.replace(final_artifact)
        try:
            updated = append_receipt(
                chain, methodology, stage, final_artifact, decision, candidate_ids,
                holdout_accessed=bool(artifact.get("holdout_accessed", False)),
                translation_exact=(artifact.get("translation_exact")
                                   if stage == "python_translation" else None),
                parity_pass=artifact.get("parity_pass") if stage == "parity" else None,
            )
            after = verify(updated, methodology_path)
        except (OSError, ValueError, TypeError) as exc:
            final_artifact.unlink(missing_ok=True)
            return {"status": "STAGE_ARTIFACT_REJECTED", "stage": stage,
                    "chain_unchanged": True, "errors": [str(exc)]}
        if not after["valid"]:
            final_artifact.unlink(missing_ok=True)
            return {"status": "STAGE_ARTIFACT_REJECTED", "stage": stage,
                    "chain_unchanged": True, "errors": after["errors"]}
        atomic_json(chain_path(state_dir), updated)
        receipt = updated["receipts"][-1]
        atomic_json(state_dir / "latest.json", {
            "campaign_id": manifest["campaign_id"], "stage": stage,
            "decision": decision, "artifact": str(final_artifact),
            "artifact_sha256": hashlib.sha256(final_artifact.read_bytes()).hexdigest(),
            "receipt_sha256": receipt["receipt_sha256"], "verification": after,
            "updated_at": now(),
        })
        return {"status": "STAGE_RECORDED", "stage": stage, "decision": decision,
                "next_stage": after["next_stage"], "terminal": after["terminal"],
                "receipt_sha256": receipt["receipt_sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("action", choices=("status", "run-next"))
    args = parser.parse_args()
    result = status(args.manifest) if args.action == "status" else run_next(args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["status"] not in {
        "INVALID", "INVALID_CHAIN", "STAGE_TIMEOUT", "STAGE_COMMAND_FAILED",
        "MANIFEST_CHANGED",
        "STAGE_ARTIFACT_MISSING", "STAGE_ARTIFACT_INVALID_JSON",
        "STAGE_ARTIFACT_INVALID_CONTRACT", "STAGE_ARTIFACT_REJECTED"} else 2)


if __name__ == "__main__":
    main()
