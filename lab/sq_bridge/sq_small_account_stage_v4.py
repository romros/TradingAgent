#!/usr/bin/env python3
"""Orchestrate source-bound 200-USDC economics after robustness passes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.small_account_artifact_v4 import build_artifact
from lab.sq_bridge.small_account_trace_v4 import derive, rebuild_from_trace
from lab.sq_bridge.candle_source_contract_v4 import verify as verify_candle_contract
from lab.sq_bridge.sq_temporal_trace_v4 import rebuild_from_trace as rebuild_temporal


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


def run_stage(*, campaign_id: str, robustness_artifact_path: Path,
              methodology_path: Path, cost_model_path: Path,
              candles_path: Path, candle_timezone: str,
              candle_contract_path: Path,
              work_dir: Path, artifact_path: Path,
              derive_fn: Callable[..., dict] = derive,
              artifact_fn: Callable[..., dict] = build_artifact) -> dict:
    robustness_artifact_path = robustness_artifact_path.resolve()
    robustness = json.loads(robustness_artifact_path.read_text())
    candidate_ids = robustness.get("candidate_ids")
    robust_metrics = robustness.get("candidate_robustness_metrics")
    if (robustness.get("stage") != "robustness"
            or robustness.get("decision") != "PASS"
            or robustness.get("campaign_id") != campaign_id
            or robustness.get("holdout_accessed") is not False
            or not isinstance(candidate_ids, list) or not candidate_ids
            or candidate_ids != sorted(set(candidate_ids))
            or not isinstance(robust_metrics, dict)
            or set(robust_metrics) != set(candidate_ids)):
        raise ValueError("ROBUSTNESS_ARTIFACT_NOT_PROMOTABLE_TO_SMALL_ACCOUNT")
    base = robustness_artifact_path.parent
    temporal_path = _resolve(
        base, robustness.get("temporal_validation_artifact_path"),
        robustness.get("temporal_validation_artifact_sha256"),
        "temporal validation artifact")
    temporal = json.loads(temporal_path.read_text())
    temporal_evidence = temporal.get("supervised_retest_evidence")
    if (temporal.get("stage") != "temporal_validation"
            or temporal.get("campaign_id") != campaign_id
            or not isinstance(temporal_evidence, dict)
            or not set(candidate_ids) <= set(temporal_evidence)):
        raise ValueError("TEMPORAL_LINEAGE_MISSING_FOR_SMALL_ACCOUNT")
    cost_model = json.loads(cost_model_path.read_text())
    if (cost_model.get("decision") != "PASS_COSTS_FROZEN"
            or cost_model.get("costs_frozen") is not True):
        raise ValueError("SMALL_ACCOUNT_REQUIRES_FROZEN_OSTIUM_COSTS")
    methodology = json.loads(methodology_path.read_text())
    risk_pct = methodology["small_account"]["maximum_risk_per_trade_pct"]
    candle_contract_raw = json.loads(candle_contract_path.read_text())
    candle_contract = verify_candle_contract(candle_contract_raw)
    if (candle_contract != candle_contract_raw
            or candle_contract.get("decision") != "PASS_CANDLE_PARITY"
            or candle_contract.get("performance_accessed") is not False
            or candle_contract.get("sq_candles_sha256") != _sha(candles_path)
            or candle_contract.get("sq_timezone") != candle_timezone
            or candle_contract.get("minimum_required_pct")
                < methodology["market_preflight"]["minimum_proxy_candle_coverage_pct"]):
        raise ValueError("SMALL_ACCOUNT_REQUIRES_VERIFIED_SQ_DUKASCOPY_CANDLES")
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    traces, evidence = [], {}
    temporal_base = temporal_path.parent
    for candidate_id in candidate_ids:
        source = temporal_evidence[candidate_id]
        temporal_trace_path = _resolve(
            temporal_base, source.get("temporal_trace_path"),
            source.get("temporal_trace_sha256"),
            f"temporal trace {candidate_id}")
        temporal_trace = json.loads(temporal_trace_path.read_text())
        if (rebuild_temporal(temporal_trace) != temporal_trace
                or temporal_trace.get("candidate_id") != candidate_id):
            raise ValueError(f"temporal trace not reproducible: {candidate_id}")
        trace = derive_fn(
            candidate_id=candidate_id,
            temporal_trace_path=temporal_trace_path,
            candles_path=candles_path, candle_timezone=candle_timezone,
            candle_contract_path=candle_contract_path,
            cost_model_path=cost_model_path,
            venue_max_leverage=robust_metrics[candidate_id]["venue_max_leverage"],
            risk_per_trade_pct=risk_pct)
        trace_path = work_dir / f"{hashlib.sha256(candidate_id.encode()).hexdigest()[:16]}.small-account.trace.json"
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
        if trace.get("source") != "synthetic_control" \
                and rebuild_from_trace(trace) != trace:
            raise ValueError(f"small-account trace not reproducible: {candidate_id}")
        traces.append(trace_path)
        evidence[candidate_id] = {
            "small_account_trace_path": str(trace_path),
            "small_account_trace_sha256": _sha(trace_path),
            "temporal_trace_path": str(temporal_trace_path),
            "temporal_trace_sha256": _sha(temporal_trace_path),
        }
    artifact = artifact_fn(
        campaign_id=campaign_id, trace_paths=traces,
        robustness_artifact_path=robustness_artifact_path,
        cost_model_path=cost_model_path,
        methodology_path=methodology_path, artifact_path=artifact_path)
    artifact.update({
        "small_account_source_evidence": evidence,
        "candles_path": str(candles_path.resolve()),
        "candles_sha256": _sha(candles_path),
        "candle_contract_path": str(candle_contract_path.resolve()),
        "candle_contract_sha256": _sha(candle_contract_path),
        "candle_timezone": candle_timezone,
        "methodology_path": str(methodology_path.resolve()),
        "methodology_sha256": _sha(methodology_path),
        "sizing_semantics": "per_trade_risk_budget_over_reconstructed_initial_sq_stop",
    })
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--robustness-artifact", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--candles", required=True, type=Path)
    parser.add_argument("--candle-timezone", required=True)
    parser.add_argument("--candle-contract", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        robustness_artifact_path=args.robustness_artifact,
        methodology_path=args.methodology, cost_model_path=args.cost_model,
        candles_path=args.candles, candle_timezone=args.candle_timezone,
        candle_contract_path=args.candle_contract,
        work_dir=args.work_dir, artifact_path=args.artifact_output)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
