import hashlib
import json
from pathlib import Path

import pytest

import lab.sq_bridge.crypto_h4_sqcli_supervised_run_v4 as module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> Path:
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text(json.dumps({
        "project_name": "PROJECT", "attempt_budget": 100,
        "attempt_stop_guard": 4, "accepted_limit": 8,
        "wall_time_budget_minutes": 10,
    }))
    source = tmp_path / "source.cfx"
    source.write_bytes(b"source")
    imported = tmp_path / "imported.cfx"
    imported.write_bytes(b"imported")
    row = {
        "candidate_id": "alq4_test", "project_name": "PROJECT",
        "cfx_path": str(source), "cfx_sha256": _sha(source),
        "manifest_path": str(manifest), "manifest_sha256": _sha(manifest),
    }
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({
        "inputs": {}, "projects": {"alq4_test": row},
        "selected_candidate_ids": ["alq4_test"],
    }))
    imported_row = {
        "candidate_id": "alq4_test", "project_name": "PROJECT",
        "source_cfx_sha256": _sha(source),
        "imported_cfx_path": str(imported), "imported_cfx_sha256": _sha(imported),
        "has_unresolved_resources": False,
    }
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({
        "batch_sha256": _sha(batch),
        "selected_candidate_ids": ["alq4_test"],
        "projects": {"alq4_test": {"state": "VERIFIED", "project": imported_row}},
    }))
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "decision": "PASS_CRYPTO_SQCLI_IMPORT", "sqcli_started": False,
        "selected_candidate_ids": ["alq4_test"],
        "batch_path": str(batch), "batch_sha256": _sha(batch),
        "checkpoint_path": str(checkpoint), "checkpoint_sha256": _sha(checkpoint),
        "projects": {"alq4_test": imported_row},
    }))
    return receipt


def _monitor(**kwargs):
    final_log = kwargs["status_file"].with_suffix(".json.sq-final.log")
    final_log.write_text("TASK FINISHED\n")
    status = {
        "generated": 96, "in_databank": 1,
        "attempt_counter_source": "sq_project_final_log",
        "sq_final_log_path": str(final_log), "sq_final_log_sha256": _sha(final_log),
        "artifacts": [{"path": "candidate.sqx", "sha256": "a" * 64}],
    }
    kwargs["status_file"].write_text(json.dumps(status))
    kwargs["journal_file"].write_text("{}\n")
    return status


def _listing(status=0, strategies=0):
    return [{"projectName": "PROJECT", "runningStatus": status,
             "strategies": strategies, "hasUnresolvedResources": False}]


def test_runs_crypto_import_once_and_emits_filter_compatible_receipt(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(module, "verify_project_row", lambda _id, row, _inputs: row)
    monkeypatch.setattr(module, "verify_cfx", lambda *_args, **_kwargs: {"valid": True})
    result = module.supervised_run(
        import_receipt_path=receipt, candidate_id="alq4_test",
        output_dir=tmp_path / "run", projects_root=tmp_path / "projects",
        disk_path=tmp_path, listing_fn=lambda *_: _listing(),
        start_fn=lambda *args: starts.append(args) or {"success": True},
        monitor_fn=_monitor)
    assert result["decision"] == "PASS_CRYPTO_H4_SUPERVISED_RUN"
    assert result["accepted"] == 1 and result["databank_inventory_exact"] is True
    assert result["costs_accessed"] is False and result["oos_accessed"] is False
    assert starts == [("http://127.0.0.1:8080", "PROJECT")]


def test_refuses_tampered_import_before_start(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    payload = json.loads(receipt.read_text())
    Path(payload["batch_path"]).write_text("{}")
    starts = []
    with pytest.raises(ValueError, match="crypto source batch path/hash mismatch"):
        module.supervised_run(
            import_receipt_path=receipt, candidate_id="alq4_test",
            output_dir=tmp_path / "run",
            start_fn=lambda *args: starts.append(args), monitor_fn=_monitor)
    assert starts == []


def test_resumes_after_crash_without_starting_twice(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    starts = []
    monkeypatch.setattr(module, "verify_project_row", lambda _id, row, _inputs: row)
    monkeypatch.setattr(module, "verify_cfx", lambda *_args, **_kwargs: {"valid": True})
    common = dict(
        import_receipt_path=receipt, candidate_id="alq4_test",
        output_dir=tmp_path / "run", projects_root=tmp_path / "projects",
        disk_path=tmp_path,
        start_fn=lambda *args: starts.append(args) or {"success": True})
    with pytest.raises(RuntimeError, match="crash"):
        module.supervised_run(
            **common, listing_fn=lambda *_: _listing(),
            monitor_fn=lambda **_: (_ for _ in ()).throw(RuntimeError("crash")))
    result = module.supervised_run(
        **common, listing_fn=lambda *_: _listing(status=1, strategies=1),
        monitor_fn=_monitor)
    assert result["decision"] == "PASS_CRYPTO_H4_SUPERVISED_RUN"
    assert len(starts) == 1


def test_finished_receipt_is_idempotent_without_touching_sq(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    monkeypatch.setattr(module, "verify_project_row", lambda _id, row, _inputs: row)
    monkeypatch.setattr(module, "verify_cfx", lambda *_args, **_kwargs: {"valid": True})
    common = dict(import_receipt_path=receipt, candidate_id="alq4_test",
                  output_dir=tmp_path / "run", projects_root=tmp_path / "projects",
                  disk_path=tmp_path)
    first = module.supervised_run(
        **common, listing_fn=lambda *_: _listing(),
        start_fn=lambda *_: {"success": True}, monitor_fn=_monitor)
    second = module.supervised_run(
        **common,
        listing_fn=lambda *_: (_ for _ in ()).throw(AssertionError("SQ touched")),
        start_fn=lambda *_: (_ for _ in ()).throw(AssertionError("SQ started")),
        monitor_fn=lambda **_: (_ for _ in ()).throw(AssertionError("SQ monitored")))
    assert second == first


def test_rejects_budget_overshoot_or_inventory_mismatch(tmp_path, monkeypatch):
    receipt = _fixture(tmp_path)
    monkeypatch.setattr(module, "verify_project_row", lambda _id, row, _inputs: row)
    monkeypatch.setattr(module, "verify_cfx", lambda *_args, **_kwargs: {"valid": True})

    def bad_monitor(**kwargs):
        result = _monitor(**kwargs)
        result["generated"] = 101
        result["in_databank"] = 2
        return result

    result = module.supervised_run(
        import_receipt_path=receipt, candidate_id="alq4_test",
        output_dir=tmp_path / "run", projects_root=tmp_path / "projects",
        disk_path=tmp_path, listing_fn=lambda *_: _listing(),
        start_fn=lambda *_: {"success": True}, monitor_fn=bad_monitor)
    assert result["decision"] == "FAIL_CRYPTO_H4_SUPERVISED_RUN"
    assert result["within_hard_attempt_budget"] is False
    assert result["databank_inventory_exact"] is False
