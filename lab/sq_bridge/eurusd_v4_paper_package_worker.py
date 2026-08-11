#!/usr/bin/env python3
"""Build, but never start, the paper-only package for a proven EURUSD candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.paper_package_artifact_v4 import build_artifact, verify_package
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash missing")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _verify_parity(*, parity: dict, parity_path: Path, holdout: dict,
                   holdout_path: Path, campaign_id: str,
                   candidate_id: str) -> None:
    methodology_path = _resolve(
        holdout_path.parent, holdout.get("methodology_path"),
        holdout.get("methodology_sha256"), "frozen methodology")
    errors = validate_stage_artifact(
        "parity", parity, {
            "decision": "PASS", "candidate_ids": [candidate_id],
            "holdout_accessed": False, "artifact": str(parity_path),
        }, _load(methodology_path), campaign_id, "alquimia_native")
    if errors:
        raise ValueError(f"parity artifact is not reproducible: {errors}")


def tick(*, screen_dir: Path, parity_worker_dir: Path, output_dir: Path,
         build_fn: Callable[..., dict] = build_artifact,
         verify_fn: Callable[[dict, Path], bool] = verify_package,
         parity_verify_fn: Callable[..., None] = _verify_parity,
         ) -> dict[str, Any]:
    parity_receipt_path = parity_worker_dir.resolve() / "parity_worker_receipt.json"
    if not parity_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_PARITY",
                "paper_configured": False, "paper_started": False,
                "live_authorized": False}
    parity_receipt = _load(parity_receipt_path)
    campaign_id = parity_receipt.get("campaign_id")
    if parity_receipt.get("decision") == "REJECT_PARITY":
        return {"schema_version": 1, "decision": "REJECT_PARITY",
                "campaign_id": campaign_id, "candidate_ids": [],
                "paper_configured": False, "paper_started": False,
                "live_authorized": False}
    if parity_receipt.get("decision") != "PASS_PARITY":
        raise ValueError("unsupported parity worker decision")
    ids = parity_receipt.get("candidate_ids")
    if not isinstance(ids, list) or len(ids) != 1:
        raise ValueError("parity receipt must identify exactly one candidate")
    candidate_id = ids[0]
    parity_path = _resolve(
        parity_receipt_path.parent, parity_receipt.get("parity_artifact_path"),
        parity_receipt.get("parity_artifact_sha256"), "parity artifact")
    parity = _load(parity_path)
    if (parity.get("stage") != "parity" or parity.get("decision") != "PASS"
            or parity.get("parity_pass") is not True
            or parity.get("campaign_id") != campaign_id
            or parity.get("candidate_ids") != [candidate_id]):
        raise ValueError("parity artifact is not paper-promotable")
    translation_path = _resolve(
        parity_path.parent, parity.get("translation_artifact_path"),
        parity.get("translation_artifact_sha256"), "translation artifact")
    translation = _load(translation_path)
    holdout_path = _resolve(
        translation_path.parent, translation.get("final_holdout_artifact_path"),
        translation.get("final_holdout_artifact_sha256"), "holdout artifact")
    holdout = _load(holdout_path)
    parity_verify_fn(
        parity=parity, parity_path=parity_path, holdout=holdout,
        holdout_path=holdout_path, campaign_id=campaign_id,
        candidate_id=candidate_id)
    small_path = _resolve(
        holdout_path.parent, holdout.get("small_account_artifact_path"),
        holdout.get("small_account_artifact_sha256"), "small-account artifact")
    screen_receipt_path = screen_dir.resolve() / "screen_trigger_receipt.json"
    screen_receipt = _load(screen_receipt_path)
    preflight_path = _resolve(
        screen_receipt_path.parent, screen_receipt.get("frozen_preflight_path"),
        screen_receipt.get("frozen_preflight_sha256"), "frozen market preflight")

    output_dir = output_dir.resolve()
    config_path = output_dir / f"{candidate_id}.paper.json"
    artifact_path = output_dir / "10_paper.json"
    receipt_path = output_dir / "paper_package_worker_receipt.json"
    if receipt_path.is_file():
        result = _load(receipt_path)
        package = _resolve(receipt_path.parent, result.get("paper_artifact_path"),
                           result.get("paper_artifact_sha256"), "paper artifact")
        config = _resolve(receipt_path.parent, result.get("paper_config_path"),
                          result.get("paper_config_sha256"), "paper config")
        if (package != artifact_path or config != config_path
                or result.get("decision") != "PASS_PAPER_PACKAGE"
                or result.get("candidate_ids") != [candidate_id]
                or result.get("paper_started") is not False
                or result.get("live_authorized") is not False
                or not verify_fn(_load(config), config)):
            raise ValueError("completed paper package receipt invalid")
        return result
    artifact = build_fn(
        campaign_id=campaign_id, candidate_id=candidate_id,
        source_artifact_paths={
            "market_preflight": preflight_path,
            "small_account_economics": small_path,
            "final_holdout_validation": holdout_path,
            "python_translation": translation_path,
            "parity": parity_path,
        }, config_path=config_path, artifact_path=artifact_path)
    if (artifact.get("decision") != "PASS" or not config_path.is_file()
            or not artifact_path.is_file() or not verify_fn(_load(config_path), config_path)):
        raise ValueError("paper-only package failed verification")
    result = {
        "schema_version": 1, "decision": "PASS_PAPER_PACKAGE",
        "campaign_id": campaign_id, "candidate_ids": [candidate_id],
        "paper_artifact_path": str(artifact_path),
        "paper_artifact_sha256": _sha(artifact_path),
        "paper_config_path": str(config_path),
        "paper_config_sha256": _sha(config_path),
        "paper_configured": True, "paper_started": False,
        "signer_enabled": False, "live_authorized": False,
    }
    write_atomic(receipt_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-dir", type=Path, default=campaign / "screen-bootstrap")
    parser.add_argument("--parity-worker-dir", type=Path, default=campaign / "parity-worker")
    parser.add_argument("--output-dir", type=Path, default=campaign / "paper-package-worker")
    args = parser.parse_args()
    print(json.dumps(tick(screen_dir=args.screen_dir,
                          parity_worker_dir=args.parity_worker_dir,
                          output_dir=args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
