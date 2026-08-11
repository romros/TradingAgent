#!/usr/bin/env python3
"""Rebuild observed SQ→Python parity from one probe-bound supervised Retest."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from lab.sq_bridge.parity_artifact_v4 import build_artifact
from lab.sq_bridge.python_parity_trace_v4 import build as build_python_trace
from lab.sq_bridge.sq_parity_trace_v4 import build as build_sq_trace
from lab.sq_bridge.sq_signal_probe_log import convert as convert_signal_log
from lab.sq_bridge.sqcli_supervised_retest import verify_retest_receipt
from lab.sq_bridge.sqx_execution_normalize_v4 import normalize
from lab.sq_bridge.sqx_extract import extract
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(base: Path, value: object, digest: object, label: str) -> Path:
    if not isinstance(value, str) or not value or not isinstance(digest, str):
        raise ValueError(f"{label} path/hash absent")
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (base / path).resolve()
    if not path.is_file() or _sha(path) != digest:
        raise ValueError(f"{label} path/hash mismatch")
    return path


def _relative(path: Path, base: Path) -> str:
    return os.path.relpath(path.resolve(), base.resolve())


def _semantic_ir(value: dict) -> dict:
    result = copy.deepcopy(value)
    result.pop("source_sqx_sha256", None)
    return result


def run_stage(
        *, campaign_id: str, translation_artifact_path: Path,
        retest_receipt_path: Path, market_data_path: Path,
        methodology_path: Path, work_dir: Path, artifact_path: Path,
        retest_verify_fn: Callable[..., dict] = verify_retest_receipt,
        normalize_fn: Callable[..., dict] = normalize,
        extract_fn: Callable[[Path], dict] = extract,
        signal_convert_fn: Callable[..., dict] = convert_signal_log,
        sq_trace_fn: Callable[..., dict] = build_sq_trace,
        python_trace_fn: Callable[..., dict] = build_python_trace,
        parity_fn: Callable[..., dict] = build_artifact) -> dict:
    translation_artifact_path = translation_artifact_path.resolve()
    translation = json.loads(translation_artifact_path.read_text())
    ids = translation.get("candidate_ids")
    if (translation.get("stage") != "python_translation"
            or translation.get("decision") != "PASS"
            or translation.get("campaign_id") != campaign_id
            or translation.get("translation_exact") is not True
            or translation.get("evidence_class") != "observed"
            or translation.get("holdout_accessed") is not False
            or not isinstance(ids, list) or len(ids) != 1):
        raise ValueError("TRANSLATION_NOT_PROMOTABLE_TO_PARITY")
    candidate_id = ids[0]
    if (not isinstance(candidate_id, str) or not candidate_id
            or Path(candidate_id).name != candidate_id
            or "/" in candidate_id or "\\" in candidate_id):
        raise ValueError("PARITY_CANDIDATE_ID_NOT_PATH_SAFE")
    base = translation_artifact_path.parent
    translated_sqx = _resolve(
        base, translation.get("sqx_path"), translation.get("sqx_sha256"),
        "translated SQX")
    ir_path = _resolve(
        base, translation.get("canonical_ir_path"),
        translation.get("canonical_ir_sha256"), "canonical IR")
    translated_ir = json.loads(ir_path.read_text())
    if (translated_ir.get("strategy_id") != candidate_id
            or validate_executable_ir(translated_ir)
                != translation.get("execution_contract")):
        raise ValueError("TRANSLATION_IR_CONTRACT_MISMATCH")

    retest_receipt_path = retest_receipt_path.resolve()
    retest_raw = json.loads(retest_receipt_path.read_text())
    orders_path = Path(retest_raw.get("orders_csv_path", "")).resolve()
    retest = retest_verify_fn(
        retest_receipt_path, candidate_id=candidate_id, orders_path=orders_path)
    runtime = retest.get("signal_probe_runtime")
    if (retest.get("signal_probe_enabled") is not True
            or not isinstance(runtime, dict)
            or runtime.get("decision") != "PASS_SIGNAL_PROBE_RUNTIME"):
        raise ValueError("RETEST_NOT_BOUND_TO_SIGNAL_PROBE")
    raw_log_path = _resolve(
        retest_receipt_path.parent, retest.get("signal_probe_raw_log_path"),
        retest.get("signal_probe_raw_log_sha256"), "raw signal probe log")
    build_receipt_path = _resolve(
        retest_receipt_path.parent, runtime.get("build_receipt_path"),
        runtime.get("build_receipt_sha256"), "signal probe build receipt")
    retested_sqx = _resolve(
        retest_receipt_path.parent, retest.get("retest_output_sqx_path"),
        retest.get("retest_output_sqx_sha256"), "retested SQX")
    translated_contract = extract_fn(translated_sqx)
    retested_contract = extract_fn(retested_sqx)
    if (translated_contract.get("strategy_name") != candidate_id
            or retested_contract.get("strategy_name") != candidate_id
            or translated_contract.get("strategy_xml_sha256")
                != retested_contract.get("strategy_xml_sha256")):
        raise ValueError("RETEST_STRATEGY_LOGIC_DIFFERS_FROM_TRANSLATION")
    market_data_path = market_data_path.resolve()
    if not market_data_path.is_file():
        raise ValueError("full warm-up market data absent")

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = work_dir / "normalized"
    normalized_sqx = normalized_dir / f"{candidate_id}.sqx"
    normalization_receipt = work_dir / "normalization.receipt.json"
    normalized = normalize_fn(
        source_path=retested_sqx, output_path=normalized_sqx,
        receipt_path=normalization_receipt,
        retest_receipt_path=retest_receipt_path)
    if (normalized.get("decision") != "PASS_VENUE_NEUTRAL_SQX"
            or normalized.get("strategy_xml_sha256")
                != translated_contract.get("strategy_xml_sha256")):
        raise ValueError("POST_RETEST_NORMALIZATION_INVALID")
    normalized_ir = canonical_ir(extract_fn(normalized_sqx))
    if (_semantic_ir(normalized_ir) != _semantic_ir(translated_ir)
            or validate_executable_ir(normalized_ir)
                != validate_executable_ir(translated_ir)):
        raise ValueError("POST_RETEST_IR_DIFFERS_FROM_TRANSLATION")

    signals_path = work_dir / "signals.csv"
    scoped_market_path = work_dir / "market.scoped.csv"
    signal_receipt_path = work_dir / "signal-log.receipt.json"
    signal_receipt = signal_convert_fn(
        raw_log_path=raw_log_path, sqx_path=normalized_sqx,
        market_data_path=market_data_path,
        build_receipt_path=build_receipt_path, time_unit="ms",
        signals_path=signals_path, scoped_market_path=scoped_market_path,
        receipt_path=signal_receipt_path)
    if (signal_receipt.get("decision") != "PASS_COMPLETE_SQ_SIGNAL_LOG"
            or signal_receipt.get("true_entry_signals", 0) < 1):
        raise ValueError("SIGNAL_PROBE_LOG_NOT_COMPLETE")
    evaluation_start = signal_receipt["first_logged_bar"]
    evaluation_end = signal_receipt["last_logged_bar"]

    sq_trace_path = work_dir / "sq.trace.json"
    python_trace_path = work_dir / "python.trace.json"
    sq_trace_fn(
        candidate_id=candidate_id, orders_path=orders_path,
        signals_path=signals_path, market_data_path=market_data_path,
        source_timezone="UTC", notional_usdc=200,
        output_path=sq_trace_path)
    python_trace_fn(
        ir_path, market_data_path, 200, python_trace_path,
        evaluation_start, evaluation_end)
    report_path = work_dir / "parity.report.json"
    artifact = parity_fn(
        campaign_id=campaign_id, candidate_id=candidate_id,
        sq_trace_path=sq_trace_path, python_trace_path=python_trace_path,
        methodology_path=methodology_path, report_path=report_path,
        artifact_path=artifact_path)
    lineage = {
        "translation_artifact_path": str(translation_artifact_path),
        "translation_artifact_sha256": _sha(translation_artifact_path),
        "supervised_retest_receipt_path": str(retest_receipt_path),
        "supervised_retest_receipt_sha256": _sha(retest_receipt_path),
        "signal_probe_build_receipt_path": str(build_receipt_path),
        "signal_probe_build_receipt_sha256": _sha(build_receipt_path),
        "signal_probe_raw_log_path": str(raw_log_path),
        "signal_probe_raw_log_sha256": _sha(raw_log_path),
        "signal_log_receipt_path": str(signal_receipt_path),
        "signal_log_receipt_sha256": _sha(signal_receipt_path),
        "normalization_receipt_path": str(normalization_receipt),
        "normalization_receipt_sha256": _sha(normalization_receipt),
        "full_market_data_path": str(market_data_path),
        "full_market_data_sha256": _sha(market_data_path),
        "evaluation_start": evaluation_start,
        "evaluation_end": evaluation_end,
        "probe_bound_supervised_retest": True,
        "warmup_outside_evaluation_allowed": True,
        "notional_usdc": 200,
    }
    bundle_path = work_dir / "parity-source-bundle.json"
    bundle = {
        "schema_version": 1, "decision": "PASS_PARITY_SOURCE_BUNDLE",
        "campaign_id": campaign_id, "candidate_id": candidate_id,
        **lineage,
        "sq_trace_path": str(sq_trace_path),
        "sq_trace_sha256": _sha(sq_trace_path),
        "python_trace_path": str(python_trace_path),
        "python_trace_sha256": _sha(python_trace_path),
    }
    write_atomic(bundle_path, bundle)
    artifact.update({
        "parity_source_bundle_path": _relative(bundle_path, artifact_path.parent),
        "parity_source_bundle_sha256": _sha(bundle_path),
        **lineage,
    })
    write_atomic(artifact_path, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--translation-artifact", required=True, type=Path)
    parser.add_argument("--retest-receipt", required=True, type=Path)
    parser.add_argument("--market-data", required=True, type=Path)
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    args = parser.parse_args()
    result = run_stage(
        campaign_id=args.campaign_id,
        translation_artifact_path=args.translation_artifact,
        retest_receipt_path=args.retest_receipt,
        market_data_path=args.market_data, methodology_path=args.methodology,
        work_dir=args.work_dir, artifact_path=args.artifact_output)
    print(json.dumps({key: result[key] for key in (
        "decision", "matched_signal_count", "matched_trade_count",
        "pnl_correlation")}, indent=2))


if __name__ == "__main__":
    main()
