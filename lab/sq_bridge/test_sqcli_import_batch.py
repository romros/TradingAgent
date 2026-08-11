import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import lab.sq_bridge.sqcli_import_batch as importer


SHAPE = {"islands": 4, "population_per_island": 100,
         "max_generations": 25, "nominal_evaluations": 10_000}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _batch(tmp_path):
    cfx = tmp_path / "project.cfx"
    cfx.write_bytes(b"source-cfx")
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text(json.dumps({"project_name": "PROJECT"}))
    batch = tmp_path / "project_batch.json"
    batch.write_text(json.dumps({
        "decision": "PASS_CFX_BATCH_READY", "sqcli_started": False,
        "selected_hypothesis_ids": ["h"],
        "projects": {"h": {
            "project_name": "PROJECT", "project_cfx_path": str(cfx),
            "project_cfx_sha256": _sha(cfx),
            "project_manifest_path": str(manifest),
            "project_manifest_sha256": _sha(manifest),
            "sq_genetic_shape": SHAPE}},
    }, sort_keys=True))
    return batch, cfx


def _runtime(monkeypatch, cfx, existing=False):
    calls = []
    listings = ([{"projectName": "PROJECT"}] if existing else [])
    resolved = [{"projectName": "PROJECT", "hasUnresolvedResources": False}]
    responses = iter((listings, resolved))
    monkeypatch.setattr(importer, "list_projects", lambda *_: next(responses))
    monkeypatch.setattr(importer, "gui_open_project", lambda *_: {
        "success": "ok", "projectName": "PROJECT"})
    monkeypatch.setattr(importer, "verify_genetic_project", lambda *_: SHAPE)

    def runner(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "cp"] and args[2].startswith("sqcli-docker:"):
            Path(args[3]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[3]).write_bytes(b"sq-reserialized-cfx")
        return subprocess.CompletedProcess(args, 0, "", "")
    return calls, runner


def test_imports_verified_batch_without_starting_projects(tmp_path, monkeypatch):
    batch, cfx = _batch(tmp_path)
    calls, runner = _runtime(monkeypatch, cfx)
    result = importer.import_batch(
        batch_path=batch, output_dir=tmp_path / "receipt", runner=runner)
    assert result["decision"] == "PASS_SQCLI_IMPORT"
    assert result["sqcli_started"] is False
    assert result["projects"]["h"]["source_cfx_sha256"] == _sha(cfx)
    assert any(call[:2] == ["docker", "exec"] and "rm" in call for call in calls)
    assert not any("start" in " ".join(call) for call in calls)


def test_rejects_hash_tampering_before_docker_mutation(tmp_path, monkeypatch):
    batch, cfx = _batch(tmp_path)
    calls, runner = _runtime(monkeypatch, cfx)
    cfx.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="CFX path/hash mismatch"):
        importer.import_batch(
            batch_path=batch, output_dir=tmp_path / "receipt", runner=runner)
    assert calls == []


def test_rejects_existing_sq_project_before_copy(tmp_path, monkeypatch):
    batch, cfx = _batch(tmp_path)
    calls, runner = _runtime(monkeypatch, cfx, existing=True)
    with pytest.raises(ValueError, match="project collision"):
        importer.import_batch(
            batch_path=batch, output_dir=tmp_path / "receipt", runner=runner)
    assert calls == []


def test_refuses_import_while_any_sq_project_is_running(tmp_path, monkeypatch):
    batch, cfx = _batch(tmp_path)
    calls, runner = _runtime(monkeypatch, cfx)
    monkeypatch.setattr(importer, "list_projects", lambda *_: [{
        "projectName": "ACADEMIA_BUSY", "runningStatus": 1,
        "hasUnresolvedResources": False,
    }])
    with pytest.raises(RuntimeError, match="refusing import while SQCLI projects run"):
        importer.import_batch(
            batch_path=batch, output_dir=tmp_path / "receipt", runner=runner)
    assert calls == []


def test_completed_import_is_idempotent_without_docker_mutation(tmp_path, monkeypatch):
    batch, cfx = _batch(tmp_path)
    calls, runner = _runtime(monkeypatch, cfx)
    output = tmp_path / "receipt"
    first = importer.import_batch(batch_path=batch, output_dir=output, runner=runner)
    calls.clear()
    monkeypatch.setattr(importer, "list_projects", lambda *_: [{
        "projectName": "PROJECT", "hasUnresolvedResources": False}])
    monkeypatch.setattr(
        importer, "gui_open_project",
        lambda *_: (_ for _ in ()).throw(AssertionError("project reimported")))
    second = importer.import_batch(batch_path=batch, output_dir=output, runner=runner)
    assert second == first
    assert calls == []


def test_resumes_import_intent_after_crash_without_reopening_project(tmp_path, monkeypatch):
    batch, _ = _batch(tmp_path)
    shape_calls, open_calls, export_calls = [], [], []
    monkeypatch.setattr(
        importer, "verify_genetic_project", lambda *_: shape_calls.append(1) or SHAPE)
    listing_calls = []

    def listing(*_):
        listing_calls.append(1)
        if len(listing_calls) == 1:
            return []
        return [{"projectName": "PROJECT", "hasUnresolvedResources": False}]

    monkeypatch.setattr(importer, "list_projects", listing)
    monkeypatch.setattr(
        importer, "gui_open_project",
        lambda *_: open_calls.append(1) or {"success": "ok", "projectName": "PROJECT"})

    def runner(args, **kwargs):
        if args[:2] == ["docker", "cp"] and args[2].startswith("sqcli-docker:"):
            export_calls.append(1)
            if len(export_calls) == 1:
                return subprocess.CompletedProcess(args, 1, "", "crash")
            Path(args[3]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[3]).write_bytes(b"sq-reserialized-cfx")
        return subprocess.CompletedProcess(args, 0, "", "")

    output = tmp_path / "receipt"
    with pytest.raises(RuntimeError, match="cannot verify imported CFX"):
        importer.import_batch(batch_path=batch, output_dir=output, runner=runner)
    checkpoint = json.loads((output / "import_checkpoint.json").read_text())
    assert checkpoint["projects"]["h"]["state"] == "IMPORT_INTENT"
    result = importer.import_batch(batch_path=batch, output_dir=output, runner=runner)
    assert result["decision"] == "PASS_SQCLI_IMPORT"
    assert len(open_calls) == 1
    assert len(export_calls) == 2
