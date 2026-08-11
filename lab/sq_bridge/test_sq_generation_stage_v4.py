import hashlib
import json

import pytest

from lab.sq_bridge.sq_generation_stage_v4 import run_stage


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lineage(tmp_path):
    cfx = tmp_path / "project.cfx"
    cfx.write_bytes(b"cfx")
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text("{}")
    batch = tmp_path / "batch.json"
    batch.write_text(json.dumps({"projects": {"h": {
        "project_name": "P", "project_cfx_path": str(cfx),
        "project_cfx_sha256": _sha(cfx), "project_manifest_path": str(manifest),
        "project_manifest_sha256": _sha(manifest)}}}))
    receipt = tmp_path / "import.json"
    receipt.write_text(json.dumps({
        "batch_path": str(batch), "batch_sha256": _sha(batch),
        "projects": {"h": {"project_name": "P"}}}))
    status = tmp_path / "status.json"
    status.write_text("{}")
    return receipt, cfx, manifest, status


def test_stage_resumes_run_and_derives_all_builder_inputs_from_lineage(tmp_path):
    receipt, cfx, manifest, status = _lineage(tmp_path)
    calls = {}

    def supervisor(**kwargs):
        calls["supervisor"] = kwargs
        return {"decision": "PASS_SUPERVISED_SQ_RUN", "project_name": "P",
                "watchdog_status_path": str(status),
                "watchdog_status_sha256": _sha(status)}

    def builder(**kwargs):
        calls["builder"] = kwargs
        return {"decision": "REJECT", "candidate_ids": []}

    result = run_stage(
        import_receipt_path=receipt, hypothesis_id="h", campaign_id="campaign",
        methodology_path=tmp_path / "methodology.json", run_dir=tmp_path / "run",
        output_path=tmp_path / "artifact.json", projects_root=tmp_path / "projects",
        supervisor=supervisor, builder=builder)
    assert result["decision"] == "REJECT"
    assert calls["builder"]["project_cfx"] == cfx.resolve()
    assert calls["builder"]["project_manifest_path"] == manifest.resolve()
    assert calls["builder"]["watchdog_status_path"] == status.resolve()
    assert calls["builder"]["databank_dir"] == (tmp_path / "projects/P/databanks").resolve()


def test_stage_never_builds_evidence_from_failed_supervision(tmp_path):
    receipt, _, _, _ = _lineage(tmp_path)
    built = []
    with pytest.raises(RuntimeError, match="did not pass"):
        run_stage(
            import_receipt_path=receipt, hypothesis_id="h", campaign_id="campaign",
            methodology_path=tmp_path / "methodology.json", run_dir=tmp_path / "run",
            output_path=tmp_path / "artifact.json",
            supervisor=lambda **_: {"decision": "FAIL_SUPERVISED_SQ_RUN"},
            builder=lambda **_: built.append(True))
    assert built == []
