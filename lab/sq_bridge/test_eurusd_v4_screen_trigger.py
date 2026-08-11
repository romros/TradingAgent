import json
import os
import subprocess
import sys

import pytest

import lab.sq_bridge.eurusd_v4_screen_trigger as module
from lab.sq_bridge.eurusd_v4_screen_trigger import trigger, verify_completed
from lab.sq_bridge.test_eurusd_d1_hypothesis_trace_v4 import _costs, _source, ROOT
from lab.sq_bridge.test_eurusd_v4_screen_bootstrap import _preflight


def test_blocked_preflight_waits_without_creating_state(tmp_path):
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps({
        "campaign_id": "eurusd-v4-test", "decision": "BLOCK",
        "blocking_reasons": ["EXECUTION_COSTS_NOT_FROZEN"],
    }))
    output = tmp_path / "out"
    result = trigger(
        preflight_path=preflight, source_path=tmp_path / "absent.csv",
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert result["decision"] == "WAITING_FOR_MARKET_PREFLIGHT"
    assert result["sqcli_started"] is False
    assert not output.exists()


def test_module_cli_imports_with_repository_root_only(tmp_path):
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps({
        "campaign_id": "eurusd-v4-test", "decision": "BLOCK",
        "blocking_reasons": ["EXECUTION_COSTS_NOT_FROZEN"],
    }))
    root = ROOT.parents[1]
    environment = {**os.environ, "PYTHONPATH": str(root)}
    result = subprocess.run([
        sys.executable, "-m", "lab.sq_bridge.eurusd_v4_screen_trigger",
        "--preflight", str(preflight), "--source", str(tmp_path / "absent.csv"),
        "--output-dir", str(tmp_path / "out"),
    ], cwd=root, env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "WAITING_FOR_MARKET_PREFLIGHT"
    assert not (tmp_path / "out").exists()


def test_pass_freezes_inputs_and_completed_replay_ignores_changing_latest(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, costs)
    output = tmp_path / "out"
    first = trigger(
        preflight_path=preflight, source_path=source,
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert first["decision"] in {"PASS_SCREEN_TRIGGER", "REJECT_SCREEN_TRIGGER"}
    assert first["sqcli_started"] is False
    frozen_costs = output / "frozen/costs.json"
    frozen_hash = module._sha(frozen_costs)

    # The collector is allowed to advance its mutable latest files. A completed
    # scientific screen remains bound to its immutable snapshots.
    costs.write_text(costs.read_text() + "\n")
    preflight.write_text('{"decision":"BLOCK"}\n')
    second = trigger(
        preflight_path=preflight, source_path=source,
        methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert second == first
    assert module._sha(frozen_costs) == frozen_hash
    assert verify_completed(output) == first


def test_completed_trigger_rejects_frozen_evidence_tampering(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    output = tmp_path / "out"
    trigger(preflight_path=_preflight(tmp_path, costs), source_path=source,
            methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    frozen = output / "frozen/mapping.json"
    frozen.write_text(frozen.read_text() + "\n")
    with pytest.raises(ValueError, match="source hash mismatch|preflight"):
        verify_completed(output)


def test_completed_reject_still_reopens_screen_trace(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    output = tmp_path / "out"
    result = trigger(preflight_path=_preflight(tmp_path, costs), source_path=source,
                     methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert result["decision"] == "REJECT_SCREEN_TRIGGER"
    bootstrap = json.loads((output / "run/bootstrap.json").read_text())
    trace = module.Path(bootstrap["trace_path"])
    trace.write_text(trace.read_text() + "\n")
    with pytest.raises(ValueError, match="screen source hash mismatch"):
        verify_completed(output)


def test_interrupted_bootstrap_resumes_from_frozen_snapshot(tmp_path, monkeypatch):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, costs)
    output = tmp_path / "out"
    real_bootstrap = module.bootstrap
    monkeypatch.setattr(module, "bootstrap", lambda **_kwargs: (_ for _ in ()).throw(
        RuntimeError("interrupted")))
    with pytest.raises(RuntimeError, match="interrupted"):
        trigger(preflight_path=preflight, source_path=source,
                methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert json.loads((output / module.JOURNAL).read_text())["phase"] == "SNAPSHOTTED"

    # Even if latest advances during the outage, all required inputs were
    # already frozen before performance was calculated.
    costs.write_text(costs.read_text() + "\n")
    monkeypatch.setattr(module, "bootstrap", real_bootstrap)
    resumed = trigger(preflight_path=preflight, source_path=source,
                      methodology_path=ROOT / "methodology_v4.json", output_dir=output)
    assert resumed["decision"] in {"PASS_SCREEN_TRIGGER", "REJECT_SCREEN_TRIGGER"}
    assert verify_completed(output) == resumed
