import hashlib
import json
from pathlib import Path

import pytest

import lab.sq_bridge.sqcli_supervised_run as launcher


SHAPE = {"islands": 4, "population_per_island": 100,
         "max_generations": 25, "nominal_evaluations": 10_000}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path):
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text(json.dumps({
        "project_name": "PROJECT", "attempt_budget": 10_000,
        "attempt_stop_guard": 64, "accepted_limit": 64,
        "wall_time_budget_minutes": 60, "sq_genetic_shape": SHAPE,
    }))
    source_cfx = tmp_path / "source.cfx"
    source_cfx.write_bytes(b"source")
    imported_cfx = tmp_path / "imported.cfx"
    imported_cfx.write_bytes(b"imported")
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({"projects": {"h": {
        "project_name": "PROJECT", "project_cfx_path": str(source_cfx),
        "project_cfx_sha256": _sha(source_cfx),
        "project_manifest_path": str(manifest),
        "project_manifest_sha256": _sha(manifest),
        "sq_genetic_shape": SHAPE,
    }}}))
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "decision": "PASS_SQCLI_IMPORT", "sqcli_started": False,
        "batch_path": str(batch), "batch_sha256": _sha(batch),
        "projects": {"h": {
            "project_name": "PROJECT", "source_cfx_sha256": _sha(source_cfx),
            "sq_imported_cfx_path": str(imported_cfx),
            "sq_imported_cfx_sha256": _sha(imported_cfx),
            "has_unresolved_resources": False,
        }},
    }))
    return receipt


def _monitor(**kwargs):
    kwargs["status_file"].write_text(json.dumps({
        "generated": 9_980, "in_databank": 12,
        "attempt_counter_source": "sq_project_final_log"}))
    kwargs["journal_file"].write_text("{}\n")
    return {"generated": 9_980, "in_databank": 12,
            "attempt_counter_source": "sq_project_final_log"}


def test_starts_only_verified_clean_import_and_records_exact_result(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(launcher, "verify_genetic_project", lambda *_: SHAPE)
    result = launcher.supervised_run(
        import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
        projects_root=tmp_path / "projects", disk_path=tmp_path,
        listing_fn=lambda *_: [{
            "projectName": "PROJECT", "runningStatus": 0, "strategies": 0,
            "hasUnresolvedResources": False}],
        start_fn=lambda *args: starts.append(args) or {"success": "ok"},
        monitor_fn=_monitor)
    assert starts == [("http://127.0.0.1:8080", "PROJECT")]
    assert result["decision"] == "PASS_SUPERVISED_SQ_RUN"
    assert result["attempt_control_threshold"] == 9_936
    assert result["paper_authorized"] is False


def test_refuses_when_any_sq_project_is_already_running(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(launcher, "verify_genetic_project", lambda *_: SHAPE)
    with pytest.raises(RuntimeError, match="already has running"):
        launcher.supervised_run(
            import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
            listing_fn=lambda *_: [
                {"projectName": "PROJECT", "runningStatus": 0, "strategies": 0,
                 "hasUnresolvedResources": False},
                {"projectName": "OTHER", "runningStatus": 1}],
            start_fn=lambda *args: starts.append(args), monitor_fn=_monitor)
    assert starts == []
    assert not (tmp_path / "run").exists()


def test_rejects_receipt_tampering_before_start(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    payload = json.loads(receipt.read_text())
    Path(payload["batch_path"]).write_text("{}")
    starts = []
    with pytest.raises(ValueError, match="source batch path/hash mismatch"):
        launcher.supervised_run(
            import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
            start_fn=lambda *args: starts.append(args), monitor_fn=_monitor)
    assert starts == []


def test_marks_hard_budget_overshoot_as_failed_evidence(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    monkeypatch.setattr(launcher, "verify_genetic_project", lambda *_: SHAPE)

    def overshoot(**kwargs):
        kwargs["status_file"].write_text("{}")
        kwargs["journal_file"].write_text("{}\n")
        return {"generated": 10_001, "in_databank": 1,
                "attempt_counter_source": "sq_project_final_log"}

    result = launcher.supervised_run(
        import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
        listing_fn=lambda *_: [{
            "projectName": "PROJECT", "runningStatus": 0, "strategies": 0,
            "hasUnresolvedResources": False}],
        start_fn=lambda *_: {"success": "ok"}, monitor_fn=overshoot)
    assert result["decision"] == "FAIL_SUPERVISED_SQ_RUN"
    assert result["within_hard_attempt_budget"] is False


def test_completed_run_is_idempotent_without_touching_sq_again(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(launcher, "verify_genetic_project", lambda *_: SHAPE)
    kwargs = dict(
        import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
        projects_root=tmp_path / "projects", disk_path=tmp_path,
        listing_fn=lambda *_: [{
            "projectName": "PROJECT", "runningStatus": 0, "strategies": 0,
            "hasUnresolvedResources": False}],
        start_fn=lambda *args: starts.append(args) or {"success": "ok"},
        monitor_fn=_monitor)
    first = launcher.supervised_run(**kwargs)
    second = launcher.supervised_run(**{
        **kwargs,
        "listing_fn": lambda *_: (_ for _ in ()).throw(AssertionError("SQ touched")),
        "start_fn": lambda *_: (_ for _ in ()).throw(AssertionError("SQ started")),
        "monitor_fn": lambda **_: (_ for _ in ()).throw(AssertionError("SQ monitored")),
    })
    assert second == first
    assert len(starts) == 1


def test_incomplete_started_run_resumes_without_second_start(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(launcher, "verify_genetic_project", lambda *_: SHAPE)
    common = dict(
        import_receipt_path=receipt, hypothesis_id="h", output_dir=tmp_path / "run",
        projects_root=tmp_path / "projects", disk_path=tmp_path,
        start_fn=lambda *args: starts.append(args) or {"success": "ok"})
    with pytest.raises(RuntimeError, match="runner crashed"):
        launcher.supervised_run(
            **common,
            listing_fn=lambda *_: [{
                "projectName": "PROJECT", "runningStatus": 0, "strategies": 0,
                "hasUnresolvedResources": False}],
            monitor_fn=lambda **_: (_ for _ in ()).throw(RuntimeError("runner crashed")))
    assert (tmp_path / "run/start_receipt.json").is_file()
    result = launcher.supervised_run(
        **common,
        listing_fn=lambda *_: [{
            "projectName": "PROJECT", "runningStatus": 1, "strategies": 4,
            "hasUnresolvedResources": False}], monitor_fn=_monitor)
    assert result["decision"] == "PASS_SUPERVISED_SQ_RUN"
    assert len(starts) == 1
