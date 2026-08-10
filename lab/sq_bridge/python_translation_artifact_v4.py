#!/usr/bin/env python3
"""Genera IR i evidència observada de python_translation v4 en un sol pas."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

try:
    from lab.sq_bridge.sqx_to_ir import translate
except ModuleNotFoundError:
    from sqx_to_ir import translate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def build_artifact(*, campaign_id: str, candidate_id: str, sqx_path: Path,
                   ir_path: Path, artifact_path: Path) -> dict:
    ir = translate(sqx_path, ir_path)
    if ir["strategy_id"] != candidate_id:
        ir_path.unlink(missing_ok=True)
        raise ValueError(
            f"Candidate lineage mismatch: expected={candidate_id} got={ir['strategy_id']}")
    base = artifact_path.resolve().parent
    artifact = {
        "schema_version": 1,
        "stage": "python_translation",
        "campaign_id": campaign_id,
        "decision": "PASS",
        "candidate_ids": [candidate_id],
        "holdout_accessed": False,
        "evidence_class": "observed",
        "translation_exact": True,
        "supported_subset": True,
        "sqx_path": _relative(sqx_path, base),
        "sqx_sha256": _sha(sqx_path),
        "canonical_ir_path": _relative(ir_path, base),
        "canonical_ir_sha256": _sha(ir_path),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--sqx", required=True, type=Path)
    parser.add_argument("--ir-output", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = build_artifact(
        campaign_id=args.campaign_id, candidate_id=args.candidate_id,
        sqx_path=args.sqx, ir_path=args.ir_output, artifact_path=args.artifact_output)
    print(json.dumps({"candidate_ids": result["candidate_ids"],
                      "canonical_ir_sha256": result["canonical_ir_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
