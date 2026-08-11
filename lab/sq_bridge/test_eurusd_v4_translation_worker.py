import hashlib
import json

from lab.sq_bridge.eurusd_v4_translation_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _tick(**kwargs):
    kwargs.setdefault(
        "holdout_verify_fn", lambda path: json.loads(path.read_text()))
    return tick(**kwargs)


def _fixture(tmp_path, decision="PASS_FINAL_HOLDOUT"):
    holdout_dir, output = tmp_path / "holdout", tmp_path / "translation"
    holdout = _write(holdout_dir / "07_final_holdout_validation.json", {
        "stage": "final_holdout_validation", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["A"],
        "holdout_accessed": True, "holdout_evaluation_count": 1})
    _write(holdout_dir / "holdout_worker_receipt.json", {
        "decision": decision, "campaign_id": "campaign",
        "candidate_ids": ["A"] if decision.startswith("PASS") else [],
        "holdout_artifact_path": str(holdout),
        "holdout_artifact_sha256": _sha(holdout)})
    return holdout_dir, output


def test_waits_for_holdout_and_reject_is_terminal(tmp_path):
    result = _tick(holdout_worker_dir=tmp_path / "absent", output_dir=tmp_path / "out")
    assert result["decision"] == "WAITING_FOR_FINAL_HOLDOUT"
    holdout, output = _fixture(tmp_path, "REJECT_FINAL_HOLDOUT")
    called = []
    result = _tick(holdout_worker_dir=holdout, output_dir=output,
                  translation_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_FINAL_HOLDOUT"
    assert called == []


def test_translates_exact_holdout_winner_once_and_replays(tmp_path):
    holdout, output = _fixture(tmp_path)
    calls = []

    def translate(**kwargs):
        calls.append(kwargs)
        kwargs["ir_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["ir_path"].write_text("{}")
        value = {"stage": "python_translation", "decision": "PASS",
                 "candidate_ids": ["A"], "translation_exact": True}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(holdout_worker_dir=holdout, output_dir=output,
                  translation_fn=translate)
    first = _tick(**common)
    assert first["decision"] == "PASS_TRANSLATION"
    assert first["candidate_ids"] == ["A"]
    assert _tick(**common) == first
    assert len(calls) == 1


def test_changed_holdout_artifact_fails_before_translation(tmp_path):
    holdout, output = _fixture(tmp_path)
    artifact = holdout / "07_final_holdout_validation.json"
    artifact.write_text("{}")
    called = []
    try:
        _tick(holdout_worker_dir=holdout, output_dir=output,
             translation_fn=lambda **kwargs: called.append(kwargs))
    except ValueError as error:
        assert "path/hash mismatch" in str(error)
    else:
        raise AssertionError("changed holdout was accepted")
    assert called == []
