#!/usr/bin/env python3
"""Open and evaluate the sole native SQ final holdout after 200-USDC PASS."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.alquimia_retest import generate
from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candle_contract
from lab.sq_bridge.final_holdout_artifact_v4 import build_artifact
from lab.sq_bridge.final_holdout_trace_v4 import derive
from lab.sq_bridge.small_account_trace_v4 import rebuild_from_trace as rebuild_small
from lab.sq_bridge.sqcli_supervised_retest import supervised_retest
from lab.sq_bridge.temporal_split_contract_v4 import digest as split_digest
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash absent")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash no coincideix")
    return path


def run_stage(*, campaign_id: str, small_account_artifact_path: Path,
              temporal_contract_path: Path, cost_model_path: Path,
              candles_path: Path, candle_timezone: str,
              candle_contract_path: Path, source_timezone: str,
              work_dir: Path, projects_root: Path, artifact_path: Path,
              methodology_path: Path,
              generate_fn: Callable[..., dict] = generate,
              supervise_fn: Callable[..., dict] = supervised_retest,
              derive_fn: Callable[..., dict] = derive,
              artifact_fn: Callable[..., dict] = build_artifact) -> dict:
    small_account_artifact_path = small_account_artifact_path.resolve()
    sizing = json.loads(small_account_artifact_path.read_text())
    candidate_ids = sizing.get("candidate_ids")
    if (sizing.get("stage") != "small_account_economics"
            or sizing.get("decision") != "PASS"
            or sizing.get("campaign_id") != campaign_id
            or sizing.get("holdout_accessed") is not False
            or not isinstance(candidate_ids, list) or len(candidate_ids) != 1):
        raise ValueError("SMALL_ACCOUNT_NOT_PROMOTABLE_TO_FINAL_HOLDOUT")
    candidate_id = candidate_ids[0]
    cost_model_path = cost_model_path.resolve()
    if sizing.get("cost_model_sha256") != _sha(cost_model_path):
        raise ValueError("FINAL_HOLDOUT_COST_MODEL_NOT_FROZEN_WITH_SIZING")
    trace_paths, trace_hashes = (sizing.get("small_account_trace_paths"),
                                 sizing.get("small_account_trace_sha256"))
    if not isinstance(trace_paths, dict) or not isinstance(trace_hashes, dict):
        raise ValueError("SMALL_ACCOUNT_TRACE_LINEAGE_MISSING")
    selected_trace_path = _resolve(
        small_account_artifact_path.parent, trace_paths.get(candidate_id),
        trace_hashes.get(candidate_id), "selected small-account trace")
    selected_trace = json.loads(selected_trace_path.read_text())
    if rebuild_small(selected_trace) != selected_trace:
        raise ValueError("SMALL_ACCOUNT_TRACE_NOT_REPRODUCIBLE")
    candidate_sqx = _resolve(
        selected_trace_path.parent, selected_trace.get("source_sqx_path"),
        selected_trace.get("source_sqx_sha256"), "selected SQX")
    temporal_trace_path = _resolve(
        selected_trace_path.parent, selected_trace.get("temporal_trace_path"),
        selected_trace.get("temporal_trace_sha256"), "selected temporal trace")
    temporal_trace = json.loads(temporal_trace_path.read_text())
    pre_receipt = _resolve(
        temporal_trace_path.parent,
        temporal_trace.get("supervised_retest_receipt_path"),
        temporal_trace.get("supervised_retest_receipt_sha256"),
        "pre-holdout receipt")
    pre_receipt_value = json.loads(pre_receipt.read_text())
    source_cfx = _resolve(
        pre_receipt.parent, pre_receipt_value.get("source_cfx_path"),
        pre_receipt_value.get("source_cfx_sha256"), "Retest template")
    temporal_contract = json.loads(temporal_contract_path.read_text())
    if temporal_contract.get("contract_type") != "observation_position_temporal_split_v4":
        raise ValueError("FINAL_HOLDOUT_TEMPORAL_CONTRACT_INVALID")
    segments = temporal_contract["segments"]
    candle_contract = json.loads(candle_contract_path.read_text())
    if (verify_candle_contract(candle_contract) != candle_contract
            or candle_contract.get("decision") != "PASS_CANDLE_PARITY"
            or candle_contract.get("last_common_timestamp_utc", "")[:10]
                < segments["final_holdout"]["to"]):
        raise ValueError("FINAL_HOLDOUT_CANDLE_COVERAGE_INCOMPLETE")
    periods = {
        "train_from": segments["train"]["from"], "train_to": segments["train"]["to"],
        "validation_from": segments["validation"]["from"],
        "validation_to": segments["validation"]["to"],
        "oos_from": segments["oos"]["from"], "oos_to": segments["oos"]["to"],
        "holdout_from": segments["final_holdout"]["from"],
        "holdout_to": segments["final_holdout"]["to"],
    }
    work_dir = work_dir.resolve()
    candidate_dir = work_dir / hashlib.sha256(candidate_id.encode()).hexdigest()[:16]
    candidate_dir.mkdir(parents=True, exist_ok=True)
    release_manifest = candidate_dir / "holdout-release-manifest.json"
    release_value = {
        "schema_version": 1, "campaign_id": campaign_id,
        "candidate_id": candidate_id, "periods": periods,
        "temporal_contract_path": str(temporal_contract_path.resolve()),
        "temporal_contract_sha256": _sha(temporal_contract_path),
        "temporal_contract_digest": split_digest(temporal_contract),
        "small_account_artifact_path": str(small_account_artifact_path),
        "small_account_artifact_sha256": _sha(small_account_artifact_path),
        "holdout_release_authorized": True,
        "holdout_evaluation_limit": 1,
    }
    if release_manifest.exists() and json.loads(release_manifest.read_text()) != release_value:
        raise ValueError("FINAL_HOLDOUT_RELEASE_INTENT_MISMATCH")
    if not release_manifest.exists():
        write_atomic(release_manifest, release_value)
    project_name = "ALQ_HOLDOUT_" + hashlib.sha256(
        f"{campaign_id}:{candidate_id}".encode()).hexdigest()[:16].upper()
    cfx = candidate_dir / "holdout.cfx"
    manifest = generate_fn(
        source=source_cfx, output=cfx, project_name=project_name,
        stage="holdout", manifest_path=release_manifest,
        methodology_path=methodology_path, symbol=candle_contract["symbol"],
        timeframe=candle_contract["timeframe"],
        candidate_sqx=candidate_sqx, candidate_id=candidate_id,
        holdout_release_artifact=small_account_artifact_path)
    manifest_path = cfx.with_suffix(".manifest.json")
    receipt = supervise_fn(
        cfx_path=cfx, manifest_path=manifest_path,
        output_dir=candidate_dir / "supervised", projects_root=projects_root)
    if (receipt.get("holdout_accessed") is not True
            or receipt.get("holdout_evaluation_count") != 1):
        raise ValueError("FINAL_HOLDOUT_SUPERVISION_DID_NOT_PROVE_SINGLE_OPENING")
    holdout_trace = derive_fn(
        candidate_id=candidate_id, orders_path=Path(receipt["orders_csv_path"]),
        supervised_holdout_receipt_path=(candidate_dir / "supervised" /
                                         "supervised_retest_receipt.json"),
        temporal_contract_path=temporal_contract_path,
        small_account_artifact_path=small_account_artifact_path,
        cost_model_path=cost_model_path, source_timezone=source_timezone,
        candles_path=candles_path, candle_timezone=candle_timezone,
        candle_contract_path=candle_contract_path)
    trace_path = candidate_dir / "final-holdout.trace.json"
    write_atomic(trace_path, holdout_trace)
    artifact = artifact_fn(
        campaign_id=campaign_id, candidate_id=candidate_id, trace_path=trace_path,
        small_account_artifact_path=small_account_artifact_path,
        cost_model_path=cost_model_path, methodology_path=methodology_path,
        artifact_path=artifact_path)
    artifact.update({
        "supervised_holdout_receipt_path": str(
            (candidate_dir / "supervised/supervised_retest_receipt.json").resolve()),
        "supervised_holdout_receipt_sha256": _sha(
            candidate_dir / "supervised/supervised_retest_receipt.json"),
        "holdout_release_manifest_path": str(release_manifest.resolve()),
        "holdout_release_manifest_sha256": _sha(release_manifest),
        "native_sq_uncensored": manifest["performance_filters_applied_in_sq"] is False,
        "methodology_path": str(methodology_path.resolve()),
        "methodology_sha256": _sha(methodology_path),
    })
    write_atomic(artifact_path, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--small-account-artifact", required=True, type=Path)
    parser.add_argument("--temporal-contract", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--candle-timezone", required=True)
    parser.add_argument("--candle-contract", required=True, type=Path)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--projects-root", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects"))
    parser.add_argument("--artifact-output", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        small_account_artifact_path=args.small_account_artifact,
        temporal_contract_path=args.temporal_contract,
        cost_model_path=args.cost_model, candles_path=args.candles,
        candle_timezone=args.candle_timezone,
        candle_contract_path=args.candle_contract,
        source_timezone=args.source_timezone, work_dir=args.work_dir,
        projects_root=args.projects_root, artifact_path=args.artifact_output,
        methodology_path=args.methodology)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
