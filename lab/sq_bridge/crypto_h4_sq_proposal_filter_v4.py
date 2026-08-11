#!/usr/bin/env python3
"""Checkpointed SQX→grid→canonical-train filter for one crypto H4 project."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_sq_candidate_normalize_v4 import normalize
from lab.sq_bridge.crypto_h4_sq_proposal_replay_v4 import replay
from lab.sq_bridge.crypto_h4_cfx_v4 import verify_cfx
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError(f"JSON object required: {path}")
    return value


def _inventory(databank: Path) -> list[dict[str, Any]]:
    return [{"path": str(path.resolve()), "sha256": _sha(path), "size": path.stat().st_size}
            for path in sorted(databank.rglob("*.sqx"))]


def run(*, runtime_receipt_path: Path, manifest_path: Path, databank_dir: Path,
        final_log_path: Path, source_receipt_path: Path,
        preregistration_path: Path, output_dir: Path) -> dict[str, Any]:
    paths = [runtime_receipt_path, manifest_path, databank_dir, final_log_path,
             source_receipt_path, preregistration_path, output_dir]
    (runtime_receipt_path, manifest_path, databank_dir, final_log_path,
     source_receipt_path, preregistration_path, output_dir) = (
        path.resolve() for path in paths)
    runtime, manifest = _load(runtime_receipt_path), _load(manifest_path)
    if runtime.get("decision") not in {
            "PASS_SQ_CUSTOM_SIGNAL_RUNTIME_SMOKE", "PASS_CRYPTO_H4_SUPERVISED_RUN"}:
        raise ValueError("SQ runtime receipt does not authorize proposal filtering")
    cfx = Path(str(runtime.get("imported_cfx_path", ""))).resolve()
    if (not cfx.is_file() or runtime.get("imported_cfx_sha256") != _sha(cfx)
            or runtime.get("manifest_sha256") != _sha(manifest_path)
            or runtime.get("project_name") != manifest.get("project_name")
            or runtime.get("final_log_sha256") != _sha(final_log_path)
            or verify_cfx(cfx, manifest, require_archive_hash=False)["valid"] is not True):
        raise ValueError("SQ runtime lineage changed")
    inventory = _inventory(databank_dir)
    if len(inventory) != runtime.get("accepted") or not inventory:
        raise ValueError("SQ databank count differs from final runtime")
    frozen = {"runtime_receipt": {"path": str(runtime_receipt_path),
                                   "sha256": _sha(runtime_receipt_path)},
              "manifest": {"path": str(manifest_path), "sha256": _sha(manifest_path)},
              "final_log": {"path": str(final_log_path), "sha256": _sha(final_log_path)},
              "source_receipt": {"path": str(source_receipt_path),
                                  "sha256": _sha(source_receipt_path)},
              "preregistration": {"path": str(preregistration_path),
                                    "sha256": _sha(preregistration_path)},
              "databank_inventory": inventory}
    final_path = output_dir / "crypto_h4_sq_proposal_filter_v4.json"
    checkpoint_path = output_dir / "checkpoint.json"
    if final_path.is_file():
        result = _load(final_path)
        if result.get("inputs") != frozen: raise ValueError("completed proposal filter changed")
        return result
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = (_load(checkpoint_path) if checkpoint_path.is_file()
                  else {"schema_version": 1, "inputs": frozen, "proposals": {}})
    if checkpoint.get("inputs") != frozen or not isinstance(checkpoint.get("proposals"), dict):
        raise ValueError("proposal filter checkpoint changed")
    if not checkpoint_path.exists(): write_atomic(checkpoint_path, checkpoint)
    proposals = {}
    for item in inventory:
        sqx = Path(item["path"]); proposal_id = f"sqv4_{item['sha256'][:16]}"
        saved = checkpoint["proposals"].get(proposal_id)
        branch = output_dir / proposal_id
        normalized_path = branch / "normalized.json"; replay_path = branch / "train_replay.json"
        if saved is None:
            normalized = normalize(sqx=sqx, manifest_path=manifest_path,
                                   preregistration_path=preregistration_path)
            branch.mkdir(parents=True, exist_ok=True)
            write_atomic(normalized_path, normalized)
            replayed = replay(normalized_path=normalized_path,
                              source_receipt_path=source_receipt_path,
                              preregistration_path=preregistration_path)
            write_atomic(replay_path, replayed)
            saved = {"state": "VERIFIED", "proposal_id": proposal_id,
                     "sqx_path": str(sqx), "sqx_sha256": item["sha256"],
                     "normalized_path": str(normalized_path),
                     "normalized_sha256": _sha(normalized_path),
                     "replay_path": str(replay_path), "replay_sha256": _sha(replay_path),
                     "decision": replayed["decision"]}
            checkpoint["proposals"][proposal_id] = saved
            write_atomic(checkpoint_path, checkpoint)
        for key in ("normalized", "replay"):
            path = Path(saved[f"{key}_path"])
            if not path.is_file() or _sha(path) != saved[f"{key}_sha256"]:
                raise ValueError(f"checkpointed {key} changed: {proposal_id}")
        proposals[proposal_id] = saved
    survivors = sorted(key for key, row in proposals.items()
                       if row["decision"] == "PASS_GROSS_REQUIRES_FROZEN_COST_GATE")
    rejected = sorted(set(proposals) - set(survivors))
    result = {"schema_version": 1, "stage": "crypto_h4_sq_proposal_filter",
              "decision": ("PASS_GROSS_SURVIVORS" if survivors
                           else "REJECT_ALL_SQ_PROPOSALS_AT_GROSS_GATE"),
              "inputs": frozen, "proposal_ids": sorted(proposals),
              "proposals": proposals, "gross_survivor_ids": survivors,
              "rejected_ids": rejected, "costs_accessed": False,
              "validation_accessed": False, "oos_accessed": False,
              "holdout_accessed": False, "strategy_promotion_authorized": False,
              "next_stage": ("frozen_ostium_cost_gate" if survivors else None)}
    write_atomic(final_path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-receipt", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--databank", required=True, type=Path)
    parser.add_argument("--final-log", required=True, type=Path)
    parser.add_argument("--source-receipt", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = run(runtime_receipt_path=args.runtime_receipt, manifest_path=args.manifest,
                 databank_dir=args.databank, final_log_path=args.final_log,
                 source_receipt_path=args.source_receipt,
                 preregistration_path=args.preregistration, output_dir=args.output_dir)
    print(json.dumps({key: result[key] for key in
                      ("decision", "proposal_ids", "gross_survivor_ids")}, indent=2))


if __name__ == "__main__": main()
