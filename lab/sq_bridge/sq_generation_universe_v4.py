#!/usr/bin/env python3
"""Freeze the complete candidate universe produced by several SQ branches."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

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


def build_universe(*, campaign_id: str,
                   generation_artifact_paths: dict[str, Path],
                   output_path: Path) -> dict[str, Any]:
    """Verify every terminal branch and emit one immutable global universe.

    Identical SQX files with the same StrategyName are safely deduplicated. A
    reused name with different bytes is an ambiguous identity and fails closed.
    REJECT branches remain in provenance but contribute no candidates.
    """
    if not generation_artifact_paths:
        raise ValueError("at least one SQ generation branch is required")
    output_path = output_path.resolve()
    output_base = output_path.parent
    candidates: dict[str, tuple[Path, str, str]] = {}
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
            existing = candidates.get(candidate_id)
            if existing is not None and existing[1] != hashes[candidate_id]:
                raise ValueError(f"candidate identity collision: {candidate_id}")
            if existing is None:
                candidates[candidate_id] = (
                    candidate_path, hashes[candidate_id], hypothesis_id)
        branch_rows[hypothesis_id] = {
            "decision": decision,
            "path": os.path.relpath(artifact_path, output_base),
            "sha256": _sha(artifact_path),
            "candidate_ids": ids,
        }

    candidate_ids = sorted(candidates)
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
        "source_generation_artifacts": branch_rows,
        "source_hypothesis_ids": sorted(branch_rows),
        "selection_policy": "complete_global_universe_before_temporal_pareto",
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
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_universe(
        campaign_id=args.campaign_id,
        generation_artifact_paths={key: Path(value)
                                   for key, value in args.generation_artifact},
        output_path=args.output)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
