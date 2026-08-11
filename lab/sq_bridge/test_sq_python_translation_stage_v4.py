import hashlib
import json

import pytest

import lab.sq_bridge.sq_python_translation_stage_v4 as module


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path, decision="PASS"):
    sqx = tmp_path / "candidate.sqx"; sqx.write_bytes(b"sqx")
    trace = tmp_path / "holdout.trace.json"
    trace.write_text(json.dumps({
        "schema_version": 2, "candidate_id": "T",
        "holdout_evaluation_count": 1,
        "source_sqx_path": str(sqx), "source_sqx_sha256": _sha(sqx)}))
    artifact = tmp_path / "holdout.json"
    artifact.write_text(json.dumps({
        "stage": "final_holdout_validation", "decision": decision,
        "campaign_id": "campaign", "candidate_ids": ["T"],
        "holdout_accessed": True, "holdout_evaluation_count": 1,
        "holdout_trace_path": str(trace), "holdout_trace_sha256": _sha(trace)}))
    return artifact


def test_translates_only_exact_reproducible_holdout_winner(tmp_path, monkeypatch):
    holdout = _inputs(tmp_path)
    monkeypatch.setattr(module, "rebuild_from_trace", lambda value: value)

    def build(**kwargs):
        assert kwargs["candidate_id"] == "T"
        assert kwargs["sqx_path"].read_bytes() == b"sqx"
        kwargs["ir_path"].write_text("{}")
        result = {"stage": "python_translation", "decision": "PASS",
                  "campaign_id": "campaign", "candidate_ids": ["T"],
                  "canonical_ir_sha256": _sha(kwargs["ir_path"])}
        kwargs["artifact_path"].write_text(json.dumps(result))
        return result
    result = module.run_stage(
        campaign_id="campaign", final_holdout_artifact_path=holdout,
        ir_path=tmp_path / "strategy.ir.json",
        artifact_path=tmp_path / "translation.json", artifact_fn=build)
    assert result["translation_source_policy"].startswith("exact_sq_strategy")
    assert result["final_holdout_artifact_sha256"] == _sha(holdout)


def test_rejects_failed_holdout_before_reading_sqx(tmp_path):
    with pytest.raises(ValueError, match="NOT_PROMOTABLE"):
        module.run_stage(
            campaign_id="campaign",
            final_holdout_artifact_path=_inputs(tmp_path, decision="REJECT"),
            ir_path=tmp_path / "ir.json", artifact_path=tmp_path / "out.json")
