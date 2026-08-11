#!/usr/bin/env python3
"""Translate only the exact candidate that passed the one-shot final holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.final_holdout_artifact_v4 import verify as verify_holdout
from lab.sq_bridge.final_holdout_trace_v4 import rebuild_from_trace
from lab.sq_bridge.python_translation_artifact_v4 import build_artifact
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash absent")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def run_stage(*, campaign_id: str, final_holdout_artifact_path: Path,
              ir_path: Path, artifact_path: Path,
              artifact_fn: Callable[..., dict] = build_artifact,
              holdout_verify_fn: Callable[[Path], dict] = verify_holdout) -> dict:
    final_holdout_artifact_path = final_holdout_artifact_path.resolve()
    holdout = holdout_verify_fn(final_holdout_artifact_path)
    ids = holdout.get("candidate_ids")
    if (holdout.get("stage") != "final_holdout_validation"
            or holdout.get("decision") != "PASS"
            or holdout.get("campaign_id") != campaign_id
            or holdout.get("holdout_accessed") is not True
            or holdout.get("holdout_evaluation_count") != 1
            or not isinstance(ids, list) or len(ids) != 1):
        raise ValueError("FINAL_HOLDOUT_NOT_PROMOTABLE_TO_TRANSLATION")
    candidate_id = ids[0]
    trace_path = _resolve(
        final_holdout_artifact_path.parent, holdout.get("holdout_trace_path"),
        holdout.get("holdout_trace_sha256"), "final holdout trace")
    trace = json.loads(trace_path.read_text())
    if (trace.get("schema_version") != 2
            or rebuild_from_trace(trace) != trace
            or trace.get("candidate_id") != candidate_id
            or trace.get("holdout_evaluation_count") != 1):
        raise ValueError("FINAL_HOLDOUT_TRACE_NOT_REPRODUCIBLE")
    sqx = _resolve(
        trace_path.parent, trace.get("source_sqx_path"),
        trace.get("source_sqx_sha256"), "final holdout SQX")
    artifact = artifact_fn(
        campaign_id=campaign_id, candidate_id=candidate_id,
        sqx_path=sqx, ir_path=ir_path, artifact_path=artifact_path)
    artifact.update({
        "final_holdout_artifact_path": str(final_holdout_artifact_path),
        "final_holdout_artifact_sha256": _sha(final_holdout_artifact_path),
        "final_holdout_trace_path": str(trace_path),
        "final_holdout_trace_sha256": _sha(trace_path),
        "translation_source_policy": "exact_sq_strategy_that_passed_single_final_holdout",
    })
    write_atomic(artifact_path, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--final-holdout-artifact", required=True, type=Path)
    parser.add_argument("--ir-output", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        final_holdout_artifact_path=args.final_holdout_artifact,
        ir_path=args.ir_output, artifact_path=args.artifact_output)
    print(json.dumps({"candidate_ids": result["candidate_ids"],
                      "canonical_ir_sha256": result["canonical_ir_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
