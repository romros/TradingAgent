#!/usr/bin/env python3
"""Orchestrate native SQ robustness for every temporal Pareto candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

from lab.sq_bridge.alquimia_monte_carlo import (
    generate as generate_mc, verify_project as verify_mc_project,
)
from lab.sq_bridge.robustness_artifact_v4 import (
    build_artifact, evaluate_trace,
)
from lab.sq_bridge.robustness_trace_v4 import derive
from lab.sq_bridge.sq_temporal_trace_v4 import rebuild_from_trace as rebuild_temporal
from lab.sq_bridge.sqcli_supervised_monte_carlo import supervised_monte_carlo
from lab.sq_bridge.sqcli_supervised_mc_exports import export_all
from lab.sq_bridge.sqx_monte_carlo_materialize import materialize


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


def _passes(row: dict, gate: dict) -> bool:
    return (row["monte_carlo_runs"] >= gate["monte_carlo_runs"]
            and row["profitable_monte_carlo_ratio"]
                >= gate["minimum_profitable_monte_carlo_ratio"]
            and row["parameter_variant_count"] >= gate["minimum_parameter_variants"]
            and row["profitable_parameter_variants_ratio"]
                >= gate["minimum_profitable_parameter_variants_ratio"]
            and row["stress_profit_factor"] >= gate["minimum_stress_profit_factor"]
            and row["liquidation_probability"]
                <= gate["maximum_liquidation_probability"])


def run_stage(
    *, campaign_id: str, temporal_artifact_path: Path,
    methodology_path: Path, cost_model_path: Path, work_dir: Path,
    host_projects_root: Path, artifact_path: Path,
    venue_max_leverage: float,
    generate_mc_fn: Callable[..., dict] = generate_mc,
    verify_mc_fn: Callable[..., dict] = verify_mc_project,
    mc_fn: Callable[..., dict] = supervised_monte_carlo,
    materialize_fn: Callable[..., dict] = materialize,
    export_fn: Callable[..., dict] = export_all,
    derive_fn: Callable[..., dict] = derive,
    evaluate_fn: Callable[..., dict] = evaluate_trace,
    artifact_fn: Callable[..., dict] = build_artifact,
) -> dict:
    temporal_artifact_path = temporal_artifact_path.resolve()
    temporal = json.loads(temporal_artifact_path.read_text())
    candidate_ids = temporal.get("candidate_ids")
    metrics = temporal.get("candidate_temporal_metrics")
    evidence = temporal.get("supervised_retest_evidence")
    if (temporal.get("stage") != "temporal_validation"
            or temporal.get("decision") != "PASS"
            or temporal.get("campaign_id") != campaign_id
            or temporal.get("holdout_accessed") is not False
            or not isinstance(candidate_ids, list) or not candidate_ids
            or candidate_ids != sorted(set(candidate_ids))
            or not isinstance(metrics, dict) or set(metrics) != set(candidate_ids)
            or not isinstance(evidence, dict)
            or not set(candidate_ids) <= set(evidence)):
        raise ValueError("TEMPORAL_ARTIFACT_NOT_PROMOTABLE_TO_ROBUSTNESS")
    methodology = json.loads(methodology_path.read_text())
    cost_model = json.loads(cost_model_path.read_text())
    if (cost_model.get("decision") != "PASS_COSTS_FROZEN"
            or cost_model.get("costs_frozen") is not True):
        raise ValueError("ROBUSTNESS_REQUIRES_FROZEN_OSTIUM_COSTS")
    robust_gate = {
        **methodology["robustness"],
        "allowed_leverage_grid": methodology["small_account"]["leverage_grid"],
    }
    leverage_grid = sorted(
        (value for value in robust_gate["allowed_leverage_grid"]
         if value <= venue_max_leverage), reverse=True)
    if not leverage_grid:
        raise ValueError("NO_LEVERAGE_ALLOWED_BY_OSTIUM_MARKET")
    cost_hash = _sha(cost_model_path)
    base = temporal_artifact_path.parent
    work_dir = work_dir.resolve()
    host_projects_root = host_projects_root.resolve()
    try:
        work_dir.relative_to(host_projects_root)
    except ValueError as exc:
        raise ValueError("ROBUSTNESS_WORK_DIR_MUST_BE_SQCLI_MOUNTED") from exc
    work_dir.mkdir(parents=True, exist_ok=True)
    selected_traces, stage_evidence = [], {}
    for candidate_id in candidate_ids:
        candidate_evidence = evidence[candidate_id]
        temporal_trace_path = _resolve(
            base, candidate_evidence.get("temporal_trace_path"),
            candidate_evidence.get("temporal_trace_sha256"),
            f"temporal trace {candidate_id}")
        temporal_trace = json.loads(temporal_trace_path.read_text())
        if (rebuild_temporal(temporal_trace) != temporal_trace
                or temporal_trace.get("candidate_id") != candidate_id):
            raise ValueError(f"temporal trace not reproducible: {candidate_id}")
        retest_receipt_path = _resolve(
            base, candidate_evidence.get("supervised_retest_receipt_path"),
            candidate_evidence.get("supervised_retest_receipt_sha256"),
            f"Retest receipt {candidate_id}")
        retest_receipt = json.loads(retest_receipt_path.read_text())
        base_cfx = Path(retest_receipt["source_cfx_path"])
        base_manifest = Path(retest_receipt["manifest_path"])
        if not base_cfx.is_file() or not base_manifest.is_file():
            raise ValueError(f"Retest lineage missing: {candidate_id}")
        token = hashlib.sha256(
            f"{campaign_id}\0{candidate_id}\0{_sha(temporal_trace_path)}".encode()
        ).hexdigest()[:16]
        candidate_dir = work_dir / token
        candidate_dir.mkdir(exist_ok=True)
        mc_cfx = candidate_dir / "parameter_monte_carlo.cfx"
        mc_manifest_path = mc_cfx.with_suffix(".manifest.json")
        if mc_cfx.is_file() or mc_manifest_path.is_file():
            if not mc_cfx.is_file() or not mc_manifest_path.is_file():
                raise ValueError(f"partial MC CFX checkpoint: {candidate_id}")
            mc_manifest = json.loads(mc_manifest_path.read_text())
            mc_contract = verify_mc_fn(mc_cfx, mc_manifest)
            if mc_contract["candidate_id"] != candidate_id:
                raise ValueError(f"MC CFX checkpoint mismatch: {candidate_id}")
        else:
            generate_mc_fn(
                source=base_cfx, output=mc_cfx,
                project_name=f"ALQ4_MC_{token.upper()}",
                simulations=robust_gate["monte_carlo_runs"],
                probability_pct=robust_gate["parameter_probability_pct"],
                max_change_pct=robust_gate["parameter_perturbation_pct"],
                base_retest_manifest_path=base_manifest)
        mc_receipt = mc_fn(
            cfx_path=mc_cfx, manifest_path=mc_manifest_path,
            output_dir=candidate_dir / "mc_run",
            projects_root=host_projects_root)
        if (mc_receipt.get("decision") != "PASS_SUPERVISED_MONTE_CARLO"
                or mc_receipt.get("candidate_id") != candidate_id):
            raise ValueError(f"supervised Monte Carlo failed: {candidate_id}")
        mc_receipt_path = candidate_dir / "mc_run/supervised_monte_carlo_receipt.json"
        native_sqx = Path(mc_receipt["retest_output_sqx_path"])
        materialization = materialize_fn(
            native_sqx, candidate_dir / "materialized",
            simulations=robust_gate["monte_carlo_runs"],
            probability_pct=robust_gate["parameter_probability_pct"],
            max_change_pct=robust_gate["parameter_perturbation_pct"],
            supervised_mc_receipt=mc_receipt_path)
        if materialization.get("evidence_class") != "observed":
            raise ValueError(f"MC materialization is not observed: {candidate_id}")
        materialization_manifest = candidate_dir / "materialized/materialization.manifest.json"
        exports = export_fn(
            materialization_manifest=materialization_manifest,
            output_dir=candidate_dir / "exports",
            host_projects_root=host_projects_root)
        if (exports.get("decision") != "PASS_SUPERVISED_MC_EXPORTS"
                or exports.get("completed_count") != robust_gate["monte_carlo_runs"]):
            raise ValueError(f"MC exports incomplete: {candidate_id}")
        export_receipt = candidate_dir / "exports/supervised-mc-exports.receipt.json"
        scans = []
        chosen_path = None
        for leverage in leverage_grid:
            trace = derive_fn(
                candidate_id=candidate_id,
                temporal_trace_path=temporal_trace_path,
                mc_export_receipt_path=export_receipt,
                cost_model_path=cost_model_path,
                tested_leverage=leverage,
                venue_max_leverage=venue_max_leverage,
                monte_carlo_runs=robust_gate["monte_carlo_runs"],
                random_seed=robust_gate["monte_carlo_seed"],
                maximum_parameter_perturbation_pct=
                    robust_gate["parameter_perturbation_pct"])
            trace_path = candidate_dir / f"robustness-L{leverage}.trace.json"
            trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
            row = evaluate_fn(trace, robust_gate, cost_model, cost_hash)
            scans.append({"leverage": leverage, "passes": _passes(row, robust_gate),
                          "metrics": row, "trace_path": str(trace_path),
                          "trace_sha256": _sha(trace_path)})
            if scans[-1]["passes"]:
                chosen_path = trace_path
                break
        if chosen_path is None:
            chosen_path = Path(scans[-1]["trace_path"])
        selected_traces.append(chosen_path)
        stage_evidence[candidate_id] = {
            "mc_manifest_path": str(mc_manifest_path),
            "mc_manifest_sha256": _sha(mc_manifest_path),
            "supervised_mc_receipt_path": str(mc_receipt_path),
            "supervised_mc_receipt_sha256": _sha(mc_receipt_path),
            "materialization_manifest_path": str(materialization_manifest),
            "materialization_manifest_sha256": _sha(materialization_manifest),
            "mc_export_receipt_path": str(export_receipt),
            "mc_export_receipt_sha256": _sha(export_receipt),
            "leverage_scan": scans,
            "selected_trace_path": str(chosen_path),
            "selected_trace_sha256": _sha(chosen_path),
        }
    artifact = artifact_fn(
        campaign_id=campaign_id, trace_paths=selected_traces,
        cost_model_path=cost_model_path,
        methodology_path=methodology_path, artifact_path=artifact_path)
    artifact.update({
        "temporal_validation_artifact_path": str(temporal_artifact_path),
        "temporal_validation_artifact_sha256": _sha(temporal_artifact_path),
        "supervised_monte_carlo_evidence": stage_evidence,
        "leverage_selection_policy": "highest_preregistered_grid_value_passing_all_robustness_gates",
    })
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--temporal-artifact", required=True, type=Path)
    parser.add_argument("--cost-model", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--host-projects-root", required=True, type=Path)
    parser.add_argument("--venue-max-leverage", required=True, type=float)
    parser.add_argument("--artifact-output", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        temporal_artifact_path=args.temporal_artifact,
        methodology_path=args.methodology, cost_model_path=args.cost_model,
        work_dir=args.work_dir, host_projects_root=args.host_projects_root,
        artifact_path=args.artifact_output,
        venue_max_leverage=args.venue_max_leverage)
    print(json.dumps({"decision": result["decision"],
                      "candidate_ids": result["candidate_ids"]}, indent=2))


if __name__ == "__main__":
    main()
