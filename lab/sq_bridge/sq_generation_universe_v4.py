#!/usr/bin/env python3
"""Freeze the complete candidate universe produced by several SQ branches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _global_id(hypothesis_id: str, native_id: str) -> str:
    digest = hashlib.sha256(
        f"{hypothesis_id}\0{native_id}".encode("utf-8")).hexdigest()[:24]
    return f"ALQ_{digest}"


def _normalize_sqx(source: Path, destination: Path, global_id: str) -> None:
    """Copy an SQX reproducibly while changing only its StrategyName value."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(source) as incoming, zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
            names = incoming.namelist()
            if names.count("settings.xml") != 1:
                raise ValueError("candidate SQX has no unique settings.xml")
            for name in names:
                payload = incoming.read(name)
                if name == "settings.xml":
                    root = ET.fromstring(payload)
                    nodes = root.findall(".//StrategyName")
                    if len(nodes) != 1:
                        raise ValueError("candidate SQX StrategyName is not unique")
                    nodes[0].text = global_id
                    payload = ET.tostring(root, encoding="utf-8")
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100600 << 16
                outgoing.writestr(info, payload)
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def build_universe(*, campaign_id: str,
                   generation_artifact_paths: dict[str, Path],
                   expected_hypothesis_ids: list[str],
                   global_candidate_budget: int = 60,
                   output_path: Path) -> dict[str, Any]:
    """Verify every terminal branch and emit one immutable global universe.

    Identical SQX files with the same StrategyName are safely deduplicated. A
    reused name with different bytes is an ambiguous identity and fails closed.
    REJECT branches remain in provenance but contribute no candidates.
    """
    if (not isinstance(expected_hypothesis_ids, list)
            or expected_hypothesis_ids != sorted(set(expected_hypothesis_ids))
            or not expected_hypothesis_ids
            or any(not isinstance(value, str) or not value
                   for value in expected_hypothesis_ids)):
        raise ValueError("frozen expected hypothesis universe is required")
    if set(generation_artifact_paths) != set(expected_hypothesis_ids):
        raise ValueError("generation artifacts do not cover every frozen hypothesis")
    if (not isinstance(global_candidate_budget, int)
            or isinstance(global_candidate_budget, bool)
            or global_candidate_budget < 1):
        raise ValueError("global candidate budget invalid")
    if not generation_artifact_paths:
        raise ValueError("at least one SQ generation branch is required")
    output_path = output_path.resolve()
    output_base = output_path.parent
    candidates: dict[str, tuple[Path, str, str, str, Path, str]] = {}
    source_hashes: dict[str, str] = {}
    branch_rows: dict[str, dict[str, Any]] = {}
    for hypothesis_id in sorted(generation_artifact_paths):
        if not isinstance(hypothesis_id, str) or not hypothesis_id:
            raise ValueError("invalid hypothesis id")
        artifact_path = generation_artifact_paths[hypothesis_id].resolve()
        artifact = json.loads(artifact_path.read_text())
        ids = artifact.get("candidate_ids")
        paths = artifact.get("candidate_artifact_paths")
        hashes = artifact.get("candidate_artifact_hashes")
        decision = artifact.get("decision")
        if (artifact.get("stage") != "sq_generation"
                or artifact.get("campaign_id") != campaign_id
                or artifact.get("holdout_accessed") is not False
                or decision not in {"PASS", "REJECT"}
                or not isinstance(ids, list) or ids != sorted(set(ids))
                or not isinstance(paths, dict) or set(paths) != set(ids)
                or not isinstance(hashes, dict) or set(hashes) != set(ids)
                or (decision == "PASS") != bool(ids)
                or artifact.get("source_hypothesis_ids") != [hypothesis_id]):
            raise ValueError(f"SQ generation branch not aggregatable: {hypothesis_id}")
        for candidate_id in ids:
            if not isinstance(candidate_id, str) or not candidate_id:
                raise ValueError(f"invalid candidate id in branch: {hypothesis_id}")
            candidate_path = _resolve(
                artifact_path.parent, paths[candidate_id], hashes[candidate_id],
                f"candidate {candidate_id}")
            contract = extract_sqx(candidate_path)
            if (contract.get("strategy_name") != candidate_id
                    or contract.get("translation_status") != "SUPPORTED_SUBSET"):
                raise ValueError(f"candidate SQX contract mismatch: {candidate_id}")
            source_hash = hashes[candidate_id]
            # Byte-identical native SQX files are one candidate even if two
            # branches happen to emit them. Different strategies sharing SQ's
            # generic display name remain distinct through a global namespace.
            if source_hash in source_hashes:
                continue
            global_id = _global_id(hypothesis_id, candidate_id)
            normalized = output_base / "candidates" / f"{global_id}.sqx"
            _normalize_sqx(candidate_path, normalized, global_id)
            normalized_hash = _sha(normalized)
            normalized_contract = extract_sqx(normalized)
            if (normalized_contract.get("strategy_name") != global_id
                    or normalized_contract.get("translation_status")
                        != "SUPPORTED_SUBSET"):
                raise ValueError(f"normalized candidate contract mismatch: {global_id}")
            candidates[global_id] = (
                normalized, normalized_hash, hypothesis_id, candidate_id,
                candidate_path, source_hash)
            source_hashes[source_hash] = global_id
        branch_rows[hypothesis_id] = {
            "decision": decision,
            "path": os.path.relpath(artifact_path, output_base),
            "sha256": _sha(artifact_path),
            "candidate_ids": ids,
        }

    candidate_ids = sorted(candidates)
    if len(candidate_ids) > global_candidate_budget:
        raise ValueError("global SQ candidate universe exceeds frozen budget")
    result = {
        "schema_version": 1,
        "stage": "sq_generation",
        "artifact_role": "global_multi_branch_candidate_universe",
        "decision": "PASS" if candidate_ids else "REJECT",
        "campaign_id": campaign_id,
        "holdout_accessed": False,
        "future_periods_accessed": False,
        "candidate_ids": candidate_ids,
        "selected_candidate_ids": candidate_ids,
        "candidate_artifact_paths": {
            key: os.path.relpath(candidates[key][0], output_base)
            for key in candidate_ids
        },
        "candidate_artifact_hashes": {
            key: candidates[key][1] for key in candidate_ids
        },
        "candidate_source_hypothesis_ids": {
            key: candidates[key][2] for key in candidate_ids
        },
        "candidate_native_strategy_names": {
            key: candidates[key][3] for key in candidate_ids
        },
        "candidate_native_artifact_paths": {
            key: os.path.relpath(candidates[key][4], output_base)
            for key in candidate_ids
        },
        "candidate_native_artifact_hashes": {
            key: candidates[key][5] for key in candidate_ids
        },
        "source_generation_artifacts": branch_rows,
        "source_hypothesis_ids": sorted(branch_rows),
        "expected_hypothesis_ids": expected_hypothesis_ids,
        "global_candidate_budget": global_candidate_budget,
        "selection_policy": "complete_global_universe_before_temporal_pareto",
        "identity_policy": "branch_native_name_to_deterministic_ALQ_sha256_namespace",
        "paper_authorized": False,
        "live_authorized": False,
    }
    if not candidate_ids:
        result["rejection_reason"] = "NO_SQ_CANDIDATES_IN_ANY_BRANCH"
    write_atomic(output_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument(
        "--generation-artifact", action="append", nargs=2,
        metavar=("HYPOTHESIS_ID", "PATH"), required=True)
    parser.add_argument("--expected-hypothesis-id", action="append", required=True)
    parser.add_argument("--global-candidate-budget", type=int, default=60)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_universe(
        campaign_id=args.campaign_id,
        generation_artifact_paths={key: Path(value)
                                   for key, value in args.generation_artifact},
        expected_hypothesis_ids=sorted(args.expected_hypothesis_id),
        global_candidate_budget=args.global_candidate_budget,
        output_path=args.output)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
