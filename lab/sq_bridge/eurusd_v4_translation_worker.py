#!/usr/bin/env python3
"""Translate only a EURUSD candidate that passed the one-shot holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.final_holdout_artifact_v4 import verify as verify_holdout
from lab.sq_bridge.sq_python_translation_stage_v4 import run_stage
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verified(value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def tick(*, holdout_worker_dir: Path, output_dir: Path,
         translation_fn: Callable[..., dict] = run_stage,
         holdout_verify_fn: Callable[[Path], dict] = verify_holdout,
         ) -> dict[str, Any]:
    holdout_receipt_path = holdout_worker_dir.resolve() / "holdout_worker_receipt.json"
    if not holdout_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_FINAL_HOLDOUT",
                "paper_authorized": False, "live_authorized": False}
    receipt = _load(holdout_receipt_path)
    campaign_id = receipt.get("campaign_id")
    if receipt.get("decision") == "REJECT_FINAL_HOLDOUT":
        return {"schema_version": 1, "decision": "REJECT_FINAL_HOLDOUT",
                "campaign_id": campaign_id, "candidate_ids": [],
                "paper_authorized": False, "live_authorized": False}
    if receipt.get("decision") != "PASS_FINAL_HOLDOUT":
        raise ValueError("unsupported holdout worker decision")
    holdout_path = _verified(
        receipt.get("holdout_artifact_path"), receipt.get("holdout_artifact_sha256"),
        "final holdout artifact")
    holdout = holdout_verify_fn(holdout_path)
    if (holdout.get("stage") != "final_holdout_validation"
            or holdout.get("decision") != "PASS"
            or holdout.get("campaign_id") != campaign_id
            or holdout.get("candidate_ids") != receipt.get("candidate_ids")
            or holdout.get("holdout_accessed") is not True
            or holdout.get("holdout_evaluation_count") != 1):
        raise ValueError("holdout artifact does not match worker receipt")
    output_dir = output_dir.resolve()
    ir_path = output_dir / "strategy.ir.json"
    artifact_path = output_dir / "08_python_translation.json"
    final_path = output_dir / "translation_worker_receipt.json"
    if final_path.is_file():
        result = _load(final_path)
        artifact = _verified(result.get("translation_artifact_path"),
                             result.get("translation_artifact_sha256"),
                             "translation artifact")
        ir = _verified(result.get("canonical_ir_path"),
                       result.get("canonical_ir_sha256"), "canonical IR")
        if (result.get("campaign_id") != campaign_id or artifact != artifact_path
                or ir != ir_path or result.get("decision") != "PASS_TRANSLATION"):
            raise ValueError("completed translation worker receipt invalid")
        return result
    artifact = translation_fn(
        campaign_id=campaign_id, final_holdout_artifact_path=holdout_path,
        ir_path=ir_path, artifact_path=artifact_path)
    if (artifact.get("decision") != "PASS"
            or artifact.get("candidate_ids") != receipt.get("candidate_ids")
            or artifact.get("translation_exact") is not True):
        raise ValueError("translation stage did not prove exact translation")
    result = {
        "schema_version": 1, "decision": "PASS_TRANSLATION",
        "campaign_id": campaign_id, "candidate_ids": artifact["candidate_ids"],
        "translation_artifact_path": str(artifact_path),
        "translation_artifact_sha256": _sha(artifact_path),
        "canonical_ir_path": str(ir_path), "canonical_ir_sha256": _sha(ir_path),
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-worker-dir", type=Path,
                        default=campaign / "holdout-worker")
    parser.add_argument("--output-dir", type=Path,
                        default=campaign / "translation-worker")
    args = parser.parse_args()
    print(json.dumps(tick(
        holdout_worker_dir=args.holdout_worker_dir, output_dir=args.output_dir),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
