import json
from pathlib import Path

import pytest

import lab.sq_bridge.crypto_h4_custom_signal_runtime_smoke_v4 as module


def files(tmp_path: Path):
    cfx = tmp_path / "project.cfx"; cfx.write_bytes(b"cfx")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"project_name": "P"}))
    return cfx, manifest


def test_completed_runtime_is_recovered_from_authoritative_final_log(tmp_path: Path,
                                                                     monkeypatch):
    cfx, manifest = files(tmp_path)
    monkeypatch.setattr(module, "verify_cfx", lambda *args, **kwargs: {
        "enabled_blocks": ["AlquimiaH4MomentumAbove", "EnterAtMarket"]})
    result = module.run(
        project="P", imported_cfx=cfx, manifest_path=manifest,
        list_fn=lambda _: [{"projectName": "P", "runningStatus": 4,
                            "hasUnresolvedResources": False, "strategies": 1}],
        final_stats_fn=lambda container, project: {
            "generated": 413, "accepted": 1, "log_path": "/log",
            "log_sha256": "a" * 64},
        start_fn=lambda *_: pytest.fail("completed run must not restart"))
    assert result["decision"] == "PASS_SQ_CUSTOM_SIGNAL_RUNTIME_SMOKE"
    assert result["generated"] == 413 and result["accepted"] == 1
    assert result["recovered_completed_run"] is True
    assert result["strategy_promotion_authorized"] is False


def test_active_other_project_fails_before_start(tmp_path: Path, monkeypatch):
    cfx, manifest = files(tmp_path)
    monkeypatch.setattr(module, "verify_cfx", lambda *args, **kwargs: {
        "enabled_blocks": ["AlquimiaH4ChannelAbove"]})
    with pytest.raises(RuntimeError, match="not clean and idle"):
        module.run(project="P", imported_cfx=cfx, manifest_path=manifest,
                   list_fn=lambda _: [
                       {"projectName": "P", "runningStatus": 0,
                        "hasUnresolvedResources": False, "strategies": 0},
                       {"projectName": "BUSY", "runningStatus": 1}],
                   start_fn=lambda *_: pytest.fail("must fail before start"))
