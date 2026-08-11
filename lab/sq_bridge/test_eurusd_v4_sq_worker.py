import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.eurusd_v4_sq_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path, selected=("h1", "h2")):
    screen = tmp_path / "screen"; screen.mkdir()
    (screen / "screen_trigger_receipt.json").write_text("{}")
    methodology = screen / "methodology.json"; methodology.write_text("{}")
    bootstrap = screen / "bootstrap.json"; bootstrap.write_text("{}")
    scaffold = tmp_path / "scaffold.cfx"; scaffold.write_bytes(b"scaffold")
    registry = tmp_path / "registry.json"; registry.write_text("{}")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "schema_version": 1, "campaign_id": "campaign",
        "scaffold_path": str(scaffold), "scaffold_sha256": _sha(scaffold),
        "scaffold_sq_version": "143.2708",
        "registry_path": str(registry), "registry_sha256": _sha(registry),
        "auto_import": True, "auto_start_generation": True,
        "base_url": "http://sq", "sqcli_container": "sq",
        "paper_authorized": False, "live_authorized": False,
    }))
    receipt = {
        "decision": "PASS_SCREEN_TRIGGER", "campaign_id": "campaign",
        "selected_hypothesis_ids": list(selected),
        "methodology_path": str(methodology), "methodology_sha256": _sha(methodology),
        "bootstrap_path": str(bootstrap),
    }
    return screen, config, receipt


def _scaffold(*_args):
    return {"sq_version": "143.2708", "source_role": "xml_format_only"}


def test_waits_without_screen_and_creates_no_state(tmp_path):
    output = tmp_path / "out"
    result = tick(screen_dir=tmp_path / "absent", config_path=tmp_path / "absent.json",
                  output_dir=output)
    assert result["decision"] == "WAITING_FOR_SCREEN"
    assert not output.exists()


def test_screen_reject_is_terminal_without_loading_worker_config(tmp_path):
    screen = tmp_path / "screen"; screen.mkdir()
    (screen / "screen_trigger_receipt.json").write_text("{}")
    result = tick(
        screen_dir=screen, config_path=tmp_path / "absent.json",
        output_dir=tmp_path / "out",
        screen_verify_fn=lambda _: {"decision": "REJECT_SCREEN_TRIGGER",
                                    "campaign_id": "campaign"})
    assert result["decision"] == "REJECT_NO_SCREEN_HYPOTHESIS"
    assert result["selected_hypothesis_ids"] == []


def test_compiles_but_refuses_import_while_foreign_sq_project_runs(tmp_path):
    screen, config, receipt = _fixture(tmp_path, ("h1",))
    imported = []

    def compile_(**kwargs):
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "project_batch.json").write_text("{}")
        return {"projects": {"h1": {"project_name": "P1"}}}

    result = tick(
        screen_dir=screen, config_path=config, output_dir=tmp_path / "out",
        screen_verify_fn=lambda _: receipt, scaffold_validate_fn=_scaffold,
        compile_fn=compile_, listing_fn=lambda _: [{
            "projectName": "ACADEMIA", "runningStatus": 1}],
        import_fn=lambda **_: imported.append(True))
    assert result["decision"] == "WAITING_FOR_SQCLI_IDLE"
    assert result["running_projects"] == ["ACADEMIA"]
    assert imported == []


def test_runs_all_branches_sequentially_and_replays_final_receipt(tmp_path):
    screen, config, receipt = _fixture(tmp_path)
    calls = {"compile": 0, "import": 0, "run": []}

    def compile_(**kwargs):
        calls["compile"] += 1
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "project_batch.json").write_text("{}")
        return {"projects": {"h1": {"project_name": "P1"},
                             "h2": {"project_name": "P2"}}}

    def import_(**kwargs):
        calls["import"] += 1
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "sqcli_import_receipt.json").write_text("{}")
        return {"decision": "PASS_SQCLI_IMPORT"}

    def run_(**kwargs):
        hypothesis = kwargs["hypothesis_id"]
        calls["run"].append(hypothesis)
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        value = {"decision": "PASS" if hypothesis == "h1" else "REJECT",
                 "candidate_ids": ["candidate-1"] if hypothesis == "h1" else []}
        kwargs["output_path"].write_text(json.dumps(value))
        return value

    def universe_(**kwargs):
        value = {"decision": "PASS", "candidate_ids": ["candidate-1"]}
        kwargs["output_path"].write_text(json.dumps(value))
        return value

    common = dict(
        screen_dir=screen, config_path=config, output_dir=tmp_path / "out",
        screen_verify_fn=lambda _: receipt, scaffold_validate_fn=_scaffold,
        compile_fn=compile_, import_fn=import_, run_fn=run_, universe_fn=universe_,
        listing_fn=lambda _: [])
    first = tick(**common)
    assert first["decision"] == "PASS_SQ_GENERATION_ORCHESTRATED"
    assert first["candidate_ids"] == ["candidate-1"]
    assert calls["run"] == ["h1", "h2"]
    before = dict(calls); before["run"] = list(calls["run"])
    assert tick(**common) == first
    assert calls == before


def test_resumes_only_its_own_running_branch_after_interruption(tmp_path):
    screen, config, receipt = _fixture(tmp_path, ("h1",))

    def compile_(**kwargs):
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "project_batch.json").write_text("{}")
        return {"projects": {"h1": {"project_name": "P1"}}}

    def import_(**kwargs):
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        (kwargs["output_dir"] / "sqcli_import_receipt.json").write_text("{}")
        return {"decision": "PASS_SQCLI_IMPORT"}

    attempts = {"n": 0}

    def run_(**kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("worker interrupted")
        value = {"decision": "REJECT", "candidate_ids": []}
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output_path"].write_text(json.dumps(value))
        return value

    def universe_(**kwargs):
        value = {"decision": "REJECT", "candidate_ids": []}
        kwargs["output_path"].write_text(json.dumps(value))
        return value

    common = dict(
        screen_dir=screen, config_path=config, output_dir=tmp_path / "out",
        screen_verify_fn=lambda _: receipt, scaffold_validate_fn=_scaffold,
        compile_fn=compile_, import_fn=import_, run_fn=run_, universe_fn=universe_)
    with pytest.raises(RuntimeError, match="interrupted"):
        tick(**common, listing_fn=lambda _: [])
    journal = json.loads((tmp_path / "out/worker_journal.json").read_text())
    assert journal["current_hypothesis_id"] == "h1"
    resumed = tick(**common, listing_fn=lambda _: [{
        "projectName": "P1", "runningStatus": 1}])
    assert resumed["decision"] == "REJECT_NO_SQ_CANDIDATES"
    assert attempts["n"] == 2


def test_worker_cron_is_separate_locked_and_non_overlapping():
    root = Path(__file__).parents[2]
    runner = (root / "scripts/run_eurusd_v4_sq_worker.sh").read_text()
    installer = (root / "scripts/install_eurusd_v4_sq_worker_cron.sh").read_text()
    assert "eurusd_v4_sq_worker" in runner
    assert "eurusd_v4_temporal_worker" in runner
    assert "eurusd_v4_robustness_worker" in runner
    assert "TEMPORAL_DIR=" in runner
    assert "ROBUSTNESS_DIR=" in runner
    assert "PYTHONPATH=\"$ROOT\"" in runner
    assert 'LINE="*/10 * * * 1-5 flock -n $LOCK ' in installer
    assert "tradingagent-eurusd-v4-sq-worker.lock" in installer
    assert "tradingagent-ostium-research-universe-economics.lock" not in installer
