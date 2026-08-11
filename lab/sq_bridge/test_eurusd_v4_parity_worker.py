import hashlib
import json

import pytest

from lab.sq_bridge.eurusd_v4_parity_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _ref(path):
    return str(path), _sha(path)


def _fixture(tmp_path):
    campaign, candidate = "campaign", "A"
    methodology = _write(tmp_path / "methodology.json", {})
    source_cfx = _write(tmp_path / "source.cfx", {})
    source_manifest = _write(tmp_path / "source.manifest.json", {})
    candidate_sqx = _write(tmp_path / "A.sqx", {})
    pre_receipt = _write(tmp_path / "pre.receipt.json", {
        "source_cfx_path": str(source_cfx), "source_cfx_sha256": _sha(source_cfx),
        "manifest_path": str(source_manifest),
        "manifest_sha256": _sha(source_manifest)})
    contract = _write(tmp_path / "temporal-contract.json", {
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-02", "to": "2021-12-31"},
            "oos": {"from": "2022-01-02", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-02", "to": "2023-12-31"}}})
    trace = _write(tmp_path / "temporal.trace.json", {
        "temporal_split_contract_path": str(contract),
        "temporal_split_contract_sha256": _sha(contract)})
    temporal = _write(tmp_path / "04_temporal.json", {
        "stage": "temporal_validation", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "supervised_retest_evidence": {candidate: {
            "supervised_retest_receipt_path": str(pre_receipt),
            "supervised_retest_receipt_sha256": _sha(pre_receipt),
            "temporal_trace_path": str(trace),
            "temporal_trace_sha256": _sha(trace)}}})
    robustness = _write(tmp_path / "05_robustness.json", {
        "stage": "robustness", "decision": "PASS", "campaign_id": campaign,
        "candidate_ids": [candidate],
        "temporal_validation_artifact_path": str(temporal),
        "temporal_validation_artifact_sha256": _sha(temporal)})
    sizing = _write(tmp_path / "06_sizing.json", {
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "robustness_artifact_path": str(robustness),
        "robustness_artifact_sha256": _sha(robustness)})
    holdout = _write(tmp_path / "07_holdout.json", {
        "stage": "final_holdout_validation", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "holdout_accessed": True, "holdout_evaluation_count": 1,
        "methodology_path": str(methodology), "methodology_sha256": _sha(methodology),
        "small_account_artifact_path": str(sizing),
        "small_account_artifact_sha256": _sha(sizing)})
    translation = _write(tmp_path / "08_translation.json", {
        "stage": "python_translation", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "translation_exact": True, "sqx_path": str(candidate_sqx),
        "sqx_sha256": _sha(candidate_sqx),
        "final_holdout_artifact_path": str(holdout),
        "final_holdout_artifact_sha256": _sha(holdout)})
    translation_dir = tmp_path / "translation-worker"
    _write(translation_dir / "translation_worker_receipt.json", {
        "decision": "PASS_TRANSLATION", "campaign_id": campaign,
        "translation_artifact_path": str(translation),
        "translation_artifact_sha256": _sha(translation)})
    candles = _write(tmp_path / "candles.csv", "date,open,high,low,close\n")
    candle_contract = _write(tmp_path / "candle-contract.json", {
        "symbol": "EURUSD", "timeframe": "D1",
        "sq_candles_path": str(candles), "sq_candles_sha256": _sha(candles)})
    build = _write(tmp_path / "build.receipt.json", {})
    projects = tmp_path / "projects"
    projects.mkdir()
    config = _write(tmp_path / "worker-config.json", {
        "small_account_candle_contract_path": str(candle_contract),
        "small_account_candle_contract_sha256": _sha(candle_contract),
        "signal_probe_build_receipt_path": str(build),
        "signal_probe_build_receipt_sha256": _sha(build),
        "host_projects_root": str(projects), "base_url": "http://sq",
        "market": {"symbol": "EURUSD", "timeframe": "D1",
                   "source_timezone": "Etc/UTC", "ostium_pair_id": "2",
                   "ostium_pair_from": "EUR", "ostium_pair_to": "USD",
                   "ostium_category": "forex"}})
    return translation_dir, tmp_path / "parity-worker", config, temporal


def test_waits_without_translation(tmp_path):
    result = tick(translation_worker_dir=tmp_path / "missing",
                  output_dir=tmp_path / "out",
                  worker_config_path=tmp_path / "unused")
    assert result["decision"] == "WAITING_FOR_TRANSLATION"
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False


def test_captures_exact_candidate_proves_parity_once_and_replays(tmp_path):
    translation_dir, output, config, _ = _fixture(tmp_path)
    calls = {"generate": 0, "capture": 0, "parity": 0}

    def generate(**kwargs):
        calls["generate"] += 1
        kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output"].write_text("cfx")
        _write(kwargs["output"].with_suffix(".manifest.json"), {
            "candidate_id": "A", "candidate_sqx_sha256": _sha(kwargs["candidate_sqx"])})
        return {}

    def capture(**kwargs):
        calls["capture"] += 1
        receipt = _write(kwargs["output_dir"] / "probe-retest.receipt.json", {})
        value = {"decision": "PASS_SIGNAL_PROBE_RETEST_CAPTURE",
                 "candidate_id": "A", "probe_restored": True,
                 "supervised_retest_receipt_path": str(receipt),
                 "supervised_retest_receipt_sha256": _sha(receipt)}
        _write(kwargs["capture_receipt_path"], value)
        return value

    def parity(**kwargs):
        calls["parity"] += 1
        value = {"stage": "parity", "decision": "PASS", "candidate_ids": ["A"]}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(translation_worker_dir=translation_dir, output_dir=output,
                  worker_config_path=config, generate_fn=generate,
                  verify_cfx_fn=lambda *args, **kwargs: {},
                  capture_fn=capture, parity_fn=parity)
    first = tick(**common)
    assert first["decision"] == "PASS_PARITY"
    assert first["normal_sqcli_restored"] is True
    assert first["paper_authorized"] is False
    assert first["live_authorized"] is False
    assert tick(**common) == first
    assert calls == {"generate": 1, "capture": 1, "parity": 1}


def test_tampered_lineage_fails_before_sqcli_capture(tmp_path):
    translation_dir, output, config, temporal = _fixture(tmp_path)
    temporal.write_text("{}")
    called = []
    with pytest.raises(ValueError, match="path/hash mismatch"):
        tick(translation_worker_dir=translation_dir, output_dir=output,
             worker_config_path=config,
             capture_fn=lambda **kwargs: called.append(kwargs))
    assert called == []


def test_capture_must_restore_normal_sqcli(tmp_path):
    translation_dir, output, config, _ = _fixture(tmp_path)

    def generate(**kwargs):
        kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output"].write_text("cfx")
        _write(kwargs["output"].with_suffix(".manifest.json"), {
            "candidate_id": "A",
            "candidate_sqx_sha256": _sha(kwargs["candidate_sqx"])})
        return {}

    with pytest.raises(ValueError, match="restore normal SQCLI"):
        tick(translation_worker_dir=translation_dir, output_dir=output,
             worker_config_path=config, generate_fn=generate,
             verify_cfx_fn=lambda *args, **kwargs: {},
             capture_fn=lambda **kwargs: {
                 "decision": "PASS_SIGNAL_PROBE_RETEST_CAPTURE",
                 "candidate_id": "A", "probe_restored": False})
