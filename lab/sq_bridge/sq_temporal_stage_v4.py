#!/usr/bin/env python3
"""Run supervised pre-holdout Retests for every v4 SQ generation candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.alquimia_retest import generate, verify_retest_project
from lab.sq_bridge.sq_temporal_trace_v4 import derive
from lab.sq_bridge.sqcli_supervised_retest import supervised_retest
from lab.sq_bridge.sq_generation_universe_v4 import _global_id
from lab.sq_bridge.sqx_extract import extract as extract_sqx
from lab.sq_bridge.temporal_validation_artifact_v4 import build_artifact


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


def run_stage(
    *, campaign_id: str, generation_artifact_path: Path,
    retest_template_path: Path, discovery_manifest_path: Path,
    temporal_contract_path: Path,
    methodology_path: Path, cost_model_path: Path, symbol: str,
    timeframe: str, source_timezone: str, work_dir: Path,
    artifact_path: Path, resource_source_path: Path | None = None,
    resource_task_file: str = "Build-Task1.xml", slippage: float = 0,
    test_precision: int = 4,
    generate_fn: Callable[..., dict] = generate,
    retest_fn: Callable[..., dict] = supervised_retest,
    derive_fn: Callable[..., dict] = derive,
    artifact_fn: Callable[..., dict] = build_artifact,
) -> dict:
    generation_artifact_path = generation_artifact_path.resolve()
    generation = json.loads(generation_artifact_path.read_text())
    candidates = generation.get("candidate_ids")
    paths, hashes = (generation.get("candidate_artifact_paths"),
                     generation.get("candidate_artifact_hashes"))
    if (generation.get("stage") != "sq_generation"
            or generation.get("decision") != "PASS"
            or generation.get("campaign_id") != campaign_id
            or generation.get("holdout_accessed") is not False
            or not isinstance(candidates, list) or not candidates
            or any(not isinstance(value, str) or not value for value in candidates)
            or candidates != sorted(set(candidates))
            or not isinstance(paths, dict) or not isinstance(hashes, dict)
            or set(paths) != set(candidates) or set(hashes) != set(candidates)):
        raise ValueError("SQ_GENERATION_ARTIFACT_NOT_PROMOTABLE")
    base = generation_artifact_path.parent
    if generation.get("artifact_role") == "global_multi_branch_candidate_universe":
        native_names = generation.get("candidate_native_strategy_names")
        native_paths = generation.get("candidate_native_artifact_paths")
        native_hashes = generation.get("candidate_native_artifact_hashes")
        source_hypotheses = generation.get("candidate_source_hypothesis_ids")
        branches = generation.get("source_generation_artifacts")
        if (generation.get("identity_policy")
                != "branch_native_name_to_deterministic_ALQ_sha256_namespace"
                or any(not isinstance(value, dict) or set(value) != set(candidates)
                       for value in (native_names, native_paths, native_hashes,
                                     source_hypotheses))
                or not isinstance(branches, dict)):
            raise ValueError("SQ_GENERATION_IDENTITY_PROVENANCE_INVALID")
        for candidate_id in candidates:
            native_id = native_names[candidate_id]
            hypothesis_id = source_hypotheses[candidate_id]
            if (not isinstance(native_id, str) or not isinstance(hypothesis_id, str)
                    or _global_id(hypothesis_id, native_id) != candidate_id):
                raise ValueError("SQ_GENERATION_NAMESPACE_MISMATCH")
            native = _resolve(
                base, native_paths[candidate_id], native_hashes[candidate_id],
                f"native candidate {candidate_id}")
            native_contract = extract_sqx(native)
            branch = branches.get(hypothesis_id) or {}
            branch_path = _resolve(
                base, branch.get("path"), branch.get("sha256"),
                f"source branch {hypothesis_id}")
            branch_artifact = json.loads(branch_path.read_text())
            if (native_contract.get("strategy_name") != native_id
                    or native_id not in branch_artifact.get("candidate_ids", [])
                    or (branch_artifact.get("candidate_artifact_hashes") or {}).get(
                        native_id) != native_hashes[candidate_id]):
                raise ValueError("SQ_GENERATION_NATIVE_LINEAGE_MISMATCH")
    inputs = {}
    for candidate_id in candidates:
        candidate = _resolve(
            base, paths[candidate_id], hashes[candidate_id],
            f"candidate {candidate_id}")
        contract = extract_sqx(candidate)
        if (contract.get("strategy_name") != candidate_id
                or contract.get("translation_status") != "SUPPORTED_SUBSET"):
            raise ValueError(f"candidate SQX identity/subset mismatch: {candidate_id}")
        inputs[candidate_id] = candidate

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    traces, receipts = [], {}
    for candidate_id in candidates:
        candidate = inputs[candidate_id]
        token = hashlib.sha256(
            f"{campaign_id}\0{candidate_id}\0{hashes[candidate_id]}".encode()).hexdigest()[:16]
        candidate_dir = work_dir / token
        candidate_dir.mkdir(exist_ok=True)
        cfx = candidate_dir / "pre_holdout.cfx"
        manifest_path = cfx.with_suffix(".manifest.json")
        if cfx.is_file() or manifest_path.is_file():
            if not cfx.is_file() or not manifest_path.is_file():
                raise ValueError(f"partial Retest CFX checkpoint: {candidate_id}")
            retest_manifest = json.loads(manifest_path.read_text())
            verify_retest_project(cfx, retest_manifest)
            if (retest_manifest.get("candidate_id") != candidate_id
                    or retest_manifest.get("candidate_sqx_sha256") != hashes[candidate_id]):
                raise ValueError(f"Retest CFX checkpoint mismatch: {candidate_id}")
        else:
            generate_fn(
                source=retest_template_path, output=cfx,
                project_name=f"ALQ4_RT_{token.upper()}", stage="pre_holdout",
                manifest_path=discovery_manifest_path,
                methodology_path=methodology_path, symbol=symbol,
                timeframe=timeframe, resource_source=resource_source_path,
                resource_task_file=resource_task_file, slippage=slippage,
                test_precision=test_precision, money_management="fixed_size",
                fixed_size=1, keep_failed=True, candidate_sqx=candidate,
                candidate_id=candidate_id)
        receipt = retest_fn(
            cfx_path=cfx, manifest_path=manifest_path,
            output_dir=candidate_dir / "run")
        if (receipt.get("decision") != "PASS_SUPERVISED_RETEST"
                or receipt.get("candidate_id") != candidate_id
                or receipt.get("holdout_accessed") is not False):
            raise ValueError(f"supervised Retest failed: {candidate_id}")
        receipt_path = candidate_dir / "run/supervised_retest_receipt.json"
        orders = Path(receipt["orders_csv_path"])
        trace = derive_fn(
            candidate_id=candidate_id, orders_path=orders,
            temporal_contract_path=temporal_contract_path,
            cost_model_path=cost_model_path, source_timezone=source_timezone,
            retest_receipt_path=receipt_path)
        trace_path = candidate_dir / "temporal.trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
        traces.append(trace_path)
        receipts[candidate_id] = {
            "supervised_retest_receipt_path": str(receipt_path),
            "supervised_retest_receipt_sha256": _sha(receipt_path),
            "temporal_trace_path": str(trace_path),
            "temporal_trace_sha256": _sha(trace_path),
        }
    artifact = artifact_fn(
        campaign_id=campaign_id, trace_paths=traces,
        cost_model_path=cost_model_path,
        methodology_path=methodology_path, artifact_path=artifact_path)
    artifact["sq_generation_artifact_path"] = str(generation_artifact_path)
    artifact["sq_generation_artifact_sha256"] = _sha(generation_artifact_path)
    artifact["methodology_path"] = str(methodology_path.resolve())
    artifact["methodology_sha256"] = _sha(methodology_path)
    artifact["supervised_retest_evidence"] = receipts
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--generation-artifact", required=True, type=Path)
    parser.add_argument("--retest-template", required=True, type=Path)
    parser.add_argument("--discovery-manifest", required=True, type=Path)
    parser.add_argument("--temporal-contract", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    parser.add_argument("--resource-source", type=Path)
    parser.add_argument("--resource-task-file", default="Build-Task1.xml")
    parser.add_argument("--slippage", type=float, default=0)
    parser.add_argument("--test-precision", type=int, default=4)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        generation_artifact_path=args.generation_artifact,
        retest_template_path=args.retest_template,
        discovery_manifest_path=args.discovery_manifest,
        temporal_contract_path=args.temporal_contract,
        methodology_path=args.methodology, cost_model_path=args.cost_model,
        symbol=args.symbol, timeframe=args.timeframe,
        source_timezone=args.source_timezone, work_dir=args.work_dir,
        artifact_path=args.artifact_output,
        resource_source_path=args.resource_source,
        resource_task_file=args.resource_task_file, slippage=args.slippage,
        test_precision=args.test_precision)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
