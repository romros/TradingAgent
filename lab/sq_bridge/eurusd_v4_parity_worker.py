#!/usr/bin/env python3
"""Capture a fresh SQ signal trace and prove EURUSD SQ-to-Python parity."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from lab.sq_bridge.alquimia_retest import generate, verify_retest_project
from lab.sq_bridge.sq_parity_stage_v4 import run_stage
from lab.sq_bridge.sq_signal_probe_controller import capture_retest
from lab.sq_bridge.temporal_split_contract_v4 import sq_periods
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


def _require_stage(value: dict[str, Any], *, stage: str, campaign_id: str,
                   candidate_id: str) -> None:
    if (value.get("stage") != stage or value.get("decision") != "PASS"
            or value.get("campaign_id") != campaign_id
            or value.get("candidate_ids") != [candidate_id]):
        raise ValueError(f"{stage} artifact lineage mismatch")


def tick(*, translation_worker_dir: Path, output_dir: Path,
         worker_config_path: Path,
         generate_fn: Callable[..., dict] = generate,
         verify_cfx_fn: Callable[..., dict] = verify_retest_project,
         capture_fn: Callable[..., dict] = capture_retest,
         parity_fn: Callable[..., dict] = run_stage) -> dict[str, Any]:
    translation_receipt_path = (
        translation_worker_dir.resolve() / "translation_worker_receipt.json")
    if not translation_receipt_path.is_file():
        return {"schema_version": 1, "decision": "WAITING_FOR_TRANSLATION",
                "paper_authorized": False, "live_authorized": False}
    translation_receipt = _load(translation_receipt_path)
    if translation_receipt.get("decision") != "PASS_TRANSLATION":
        raise ValueError("unsupported translation worker decision")
    campaign_id = translation_receipt.get("campaign_id")
    translation_path = _resolve(
        translation_receipt_path.parent,
        translation_receipt.get("translation_artifact_path"),
        translation_receipt.get("translation_artifact_sha256"),
        "translation artifact")
    translation = _load(translation_path)
    candidate_ids = translation.get("candidate_ids")
    if (translation.get("stage") != "python_translation"
            or translation.get("decision") != "PASS"
            or translation.get("campaign_id") != campaign_id
            or translation.get("translation_exact") is not True
            or not isinstance(candidate_ids, list) or len(candidate_ids) != 1):
        raise ValueError("translation artifact not promotable to parity")
    candidate_id = candidate_ids[0]
    candidate_sqx = _resolve(
        translation_path.parent, translation.get("sqx_path"),
        translation.get("sqx_sha256"), "translated candidate SQX")
    holdout_path = _resolve(
        translation_path.parent, translation.get("final_holdout_artifact_path"),
        translation.get("final_holdout_artifact_sha256"), "final holdout artifact")
    holdout = _load(holdout_path)
    _require_stage(holdout, stage="final_holdout_validation",
                   campaign_id=campaign_id, candidate_id=candidate_id)
    if (holdout.get("holdout_accessed") is not True
            or holdout.get("holdout_evaluation_count") != 1):
        raise ValueError("final holdout was not a one-shot evaluation")
    methodology_path = _resolve(
        holdout_path.parent, holdout.get("methodology_path"),
        holdout.get("methodology_sha256"), "frozen holdout methodology")
    sizing_path = _resolve(
        holdout_path.parent, holdout.get("small_account_artifact_path"),
        holdout.get("small_account_artifact_sha256"), "small-account artifact")
    sizing = _load(sizing_path)
    _require_stage(sizing, stage="small_account_economics",
                   campaign_id=campaign_id, candidate_id=candidate_id)
    robustness_path = _resolve(
        sizing_path.parent, sizing.get("robustness_artifact_path"),
        sizing.get("robustness_artifact_sha256"), "robustness artifact")
    robustness = _load(robustness_path)
    _require_stage(robustness, stage="robustness",
                   campaign_id=campaign_id, candidate_id=candidate_id)
    temporal_path = _resolve(
        robustness_path.parent, robustness.get("temporal_validation_artifact_path"),
        robustness.get("temporal_validation_artifact_sha256"),
        "temporal validation artifact")
    temporal = _load(temporal_path)
    _require_stage(temporal, stage="temporal_validation",
                   campaign_id=campaign_id, candidate_id=candidate_id)
    source = (temporal.get("supervised_retest_evidence") or {}).get(candidate_id) or {}
    temporal_trace_path = _resolve(
        temporal_path.parent, source.get("temporal_trace_path"),
        source.get("temporal_trace_sha256"), "candidate temporal trace")
    temporal_trace = _load(temporal_trace_path)
    temporal_contract_path = _resolve(
        temporal_trace_path.parent, temporal_trace.get("temporal_split_contract_path"),
        temporal_trace.get("temporal_split_contract_sha256"),
        "frozen temporal split contract")
    temporal_contract = _load(temporal_contract_path)
    pre_receipt_path = _resolve(
        temporal_path.parent, source.get("supervised_retest_receipt_path"),
        source.get("supervised_retest_receipt_sha256"), "original pre-holdout receipt")
    pre_receipt = _load(pre_receipt_path)
    source_cfx = _resolve(
        pre_receipt_path.parent, pre_receipt.get("source_cfx_path"),
        pre_receipt.get("source_cfx_sha256"), "pre-holdout CFX source")
    _resolve(
        pre_receipt_path.parent, pre_receipt.get("manifest_path"),
        pre_receipt.get("manifest_sha256"), "pre-holdout manifest")

    config_path = worker_config_path.resolve()
    config = _load(config_path)
    candle_contract_path = _resolve(
        config_path.parent, config.get("small_account_candle_contract_path"),
        config.get("small_account_candle_contract_sha256"), "parity candle contract")
    candle_contract = _load(candle_contract_path)
    market_data_path = _resolve(
        candle_contract_path.parent, candle_contract.get("sq_candles_path"),
        candle_contract.get("sq_candles_sha256"), "full SQ parity market data")
    build_receipt_path = _resolve(
        config_path.parent, config.get("signal_probe_build_receipt_path"),
        config.get("signal_probe_build_receipt_sha256"), "signal probe build receipt")
    projects_root = Path(str(config.get("host_projects_root", ""))).resolve()
    if not projects_root.is_dir():
        raise ValueError("SQCLI projects root missing")

    output_dir = output_dir.resolve()
    artifact_path = output_dir / "09_parity.json"
    final_path = output_dir / "parity_worker_receipt.json"
    if final_path.is_file():
        result = _load(final_path)
        artifact = _resolve(final_path.parent, result.get("parity_artifact_path"),
                            result.get("parity_artifact_sha256"), "parity artifact")
        if (result.get("campaign_id") != campaign_id or artifact != artifact_path
                or result.get("candidate_ids") != [candidate_id]
                or result.get("decision") not in {"PASS_PARITY", "REJECT_PARITY"}
                or result.get("paper_authorized") is not False
                or result.get("live_authorized") is not False):
            raise ValueError("completed parity worker receipt invalid")
        return result

    cfx = output_dir / "probe-pre-holdout.cfx"
    manifest_path = cfx.with_suffix(".manifest.json")
    periods_path = output_dir / "probe-periods.json"
    periods = {
        "schema_version": 1, "campaign_id": campaign_id,
        "periods": sq_periods(temporal_contract),
        "temporal_split_contract_path": str(temporal_contract_path),
        "temporal_split_contract_sha256": _sha(temporal_contract_path),
    }
    if periods_path.is_file():
        if _load(periods_path) != periods:
            raise ValueError("parity period checkpoint mismatch")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(periods_path, periods)
    project_token = hashlib.sha256(
        f"{campaign_id}\0{candidate_id}\0{_sha(candidate_sqx)}".encode()).hexdigest()[:16]
    if cfx.is_file() or manifest_path.is_file():
        if not cfx.is_file() or not manifest_path.is_file():
            raise ValueError("partial parity Retest CFX checkpoint")
        manifest = _load(manifest_path)
        verify_cfx_fn(cfx, manifest)
        if (manifest.get("candidate_id") != candidate_id
                or manifest.get("candidate_sqx_sha256") != _sha(candidate_sqx)):
            raise ValueError("parity Retest CFX checkpoint mismatch")
    else:
        generate_fn(
            source=source_cfx, output=cfx,
            project_name=f"ALQ4_PAR_{project_token.upper()}", stage="pre_holdout",
            manifest_path=periods_path, methodology_path=methodology_path,
            symbol="EURUSD", timeframe="D1", candidate_sqx=candidate_sqx,
            candidate_id=candidate_id)
        if not cfx.is_file() or not manifest_path.is_file():
            raise ValueError("parity Retest generator did not produce its checkpoint")
        manifest = _load(manifest_path)
        verify_cfx_fn(cfx, manifest)
        if (manifest.get("candidate_id") != candidate_id
                or manifest.get("candidate_sqx_sha256") != _sha(candidate_sqx)):
            raise ValueError("generated parity Retest CFX mismatch")
    capture_dir = output_dir / "probe-capture"
    capture_receipt_path = capture_dir / "capture.receipt.json"
    capture = capture_fn(
        journal_path=capture_dir / "controller.journal.json",
        capture_receipt_path=capture_receipt_path,
        build_receipt_path=build_receipt_path, output_dir=capture_dir,
        raw_log_path=capture_dir / "signals.raw.log", cfx_path=cfx,
        manifest_path=manifest_path, retest_output_dir=capture_dir / "retest",
        projects_root=projects_root, normal_name="sqcli-docker",
        probe_name="sqcli-signal-probe", base_url=config["base_url"])
    if (capture.get("decision") != "PASS_SIGNAL_PROBE_RETEST_CAPTURE"
            or capture.get("candidate_id") != candidate_id
            or capture.get("probe_restored") is not True):
        raise ValueError("signal probe capture did not restore normal SQCLI")
    probe_retest_path = _resolve(
        capture_receipt_path.parent,
        capture.get("supervised_retest_receipt_path"),
        capture.get("supervised_retest_receipt_sha256"), "probe Retest receipt")

    artifact = parity_fn(
        campaign_id=campaign_id, translation_artifact_path=translation_path,
        retest_receipt_path=probe_retest_path, market_data_path=market_data_path,
        methodology_path=methodology_path, work_dir=output_dir / "comparison",
        artifact_path=artifact_path)
    if artifact.get("decision") not in {"PASS", "REJECT"}:
        raise ValueError("parity stage returned invalid decision")
    result = {
        "schema_version": 1,
        "decision": "PASS_PARITY" if artifact["decision"] == "PASS" else "REJECT_PARITY",
        "campaign_id": campaign_id, "candidate_ids": artifact.get("candidate_ids", []),
        "parity_artifact_path": str(artifact_path),
        "parity_artifact_sha256": _sha(artifact_path),
        "signal_probe_capture_receipt_path": str(capture_receipt_path),
        "signal_probe_capture_receipt_sha256": _sha(capture_receipt_path),
        "normal_sqcli_restored": True, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(final_path, result)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    campaign = root / "data/alquimia_v4/eurusd-d1-alquimia-v4"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-worker-dir", type=Path,
                        default=campaign / "translation-worker")
    parser.add_argument("--output-dir", type=Path, default=campaign / "parity-worker")
    parser.add_argument("--worker-config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    args = parser.parse_args()
    print(json.dumps(tick(
        translation_worker_dir=args.translation_worker_dir,
        output_dir=args.output_dir, worker_config_path=args.worker_config),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
