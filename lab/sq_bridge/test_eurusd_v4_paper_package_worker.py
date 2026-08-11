import hashlib
import json

import pytest

from lab.sq_bridge.eurusd_v4_paper_package_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _fixture(tmp_path, parity_decision="PASS_PARITY"):
    campaign, candidate = "campaign", "A"
    small = _write(tmp_path / "06_small.json", {
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate]})
    holdout = _write(tmp_path / "07_holdout.json", {
        "stage": "final_holdout_validation", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "small_account_artifact_path": str(small),
        "small_account_artifact_sha256": _sha(small)})
    translation = _write(tmp_path / "08_translation.json", {
        "stage": "python_translation", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": [candidate],
        "final_holdout_artifact_path": str(holdout),
        "final_holdout_artifact_sha256": _sha(holdout)})
    parity = _write(tmp_path / "09_parity.json", {
        "stage": "parity", "decision": "PASS", "parity_pass": True,
        "campaign_id": campaign, "candidate_ids": [candidate],
        "translation_artifact_path": str(translation),
        "translation_artifact_sha256": _sha(translation)})
    parity_dir = tmp_path / "parity-worker"
    receipt = {"decision": parity_decision, "campaign_id": campaign,
               "candidate_ids": [candidate] if parity_decision == "PASS_PARITY" else []}
    if parity_decision == "PASS_PARITY":
        receipt.update({"parity_artifact_path": str(parity),
                        "parity_artifact_sha256": _sha(parity)})
    _write(parity_dir / "parity_worker_receipt.json", receipt)
    preflight = _write(tmp_path / "01_preflight.json", {
        "stage": "market_preflight", "decision": "PASS",
        "campaign_id": campaign, "candidate_ids": []})
    screen = tmp_path / "screen"
    _write(screen / "screen_trigger_receipt.json", {
        "frozen_preflight_path": str(preflight),
        "frozen_preflight_sha256": _sha(preflight)})
    return screen, parity_dir, tmp_path / "paper"


def test_waits_for_parity_and_reject_is_terminal(tmp_path):
    result = tick(screen_dir=tmp_path / "screen",
                  parity_worker_dir=tmp_path / "missing", output_dir=tmp_path / "out")
    assert result["decision"] == "WAITING_FOR_PARITY"
    assert result["paper_started"] is False
    screen, parity, output = _fixture(tmp_path, "REJECT_PARITY")
    called = []
    result = tick(screen_dir=screen, parity_worker_dir=parity, output_dir=output,
                  build_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_PARITY"
    assert called == []


def test_builds_verified_unsigned_paper_package_once(tmp_path):
    screen, parity, output = _fixture(tmp_path)
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        _write(kwargs["config_path"], {"mode": "paper", "signer_enabled": False})
        value = {"stage": "paper", "decision": "PASS", "candidate_ids": ["A"]}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(screen_dir=screen, parity_worker_dir=parity, output_dir=output,
                  build_fn=build, verify_fn=lambda config, path: (
                      config.get("mode") == "paper"
                      and config.get("signer_enabled") is False))
    first = tick(**common)
    assert first["decision"] == "PASS_PAPER_PACKAGE"
    assert first["paper_configured"] is True
    assert first["paper_started"] is False
    assert first["signer_enabled"] is False
    assert first["live_authorized"] is False
    assert tick(**common) == first
    assert len(calls) == 1


def test_tampered_parity_fails_before_package_build(tmp_path):
    screen, parity, output = _fixture(tmp_path)
    parity_artifact = tmp_path / "09_parity.json"
    parity_artifact.write_text("{}")
    called = []
    with pytest.raises(ValueError, match="path/hash mismatch"):
        tick(screen_dir=screen, parity_worker_dir=parity, output_dir=output,
             build_fn=lambda **kwargs: called.append(kwargs))
    assert called == []
