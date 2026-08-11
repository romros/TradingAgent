import hashlib
import json
from pathlib import Path

import lab.sq_bridge.crypto_h4_sq_proposal_filter_v4 as module


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def test_filter_checkpoints_each_sqx_and_returns_no_false_survivor(tmp_path: Path,
                                                                  monkeypatch):
    cfx = tmp_path / "project.cfx"; cfx.write_bytes(b"cfx")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"project_name": "P"}))
    log = tmp_path / "final.log"; log.write_text("finished")
    source = tmp_path / "source.json"; source.write_text("{}")
    prereg = tmp_path / "prereg.json"; prereg.write_text("{}")
    databank = tmp_path / "databank"; databank.mkdir()
    (databank / "candidate.sqx").write_bytes(b"sqx")
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps({
        "decision": "PASS_CRYPTO_H4_SUPERVISED_RUN", "project_name": "P",
        "imported_cfx_path": str(cfx), "imported_cfx_sha256": sha(cfx),
        "manifest_sha256": sha(manifest), "final_log_sha256": sha(log), "accepted": 1}))
    monkeypatch.setattr(module, "verify_cfx", lambda *args, **kwargs: {"valid": True})
    monkeypatch.setattr(module, "normalize", lambda **kwargs: {
        "decision": "PASS_NORMALIZED_SQ_PROPOSAL_NOT_CANDIDATE"})
    monkeypatch.setattr(module, "replay", lambda **kwargs: {
        "decision": "REJECT_SQ_PROPOSAL_CANONICAL_GROSS"})
    output = tmp_path / "out"
    result = module.run(runtime_receipt_path=runtime, manifest_path=manifest,
                        databank_dir=databank, final_log_path=log,
                        source_receipt_path=source, preregistration_path=prereg,
                        output_dir=output)
    assert result["decision"] == "REJECT_ALL_SQ_PROPOSALS_AT_GROSS_GATE"
    assert len(result["proposal_ids"]) == 1 and result["gross_survivor_ids"] == []
    assert result["costs_accessed"] is False
    assert module.run(runtime_receipt_path=runtime, manifest_path=manifest,
                      databank_dir=databank, final_log_path=log,
                      source_receipt_path=source, preregistration_path=prereg,
                      output_dir=output) == result
