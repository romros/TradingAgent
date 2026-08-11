import hashlib
import json

import pytest

from lab.sq_bridge.eurusd_v4_robustness_worker import tick, venue_max_leverage


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _costs():
    row = {"min": 200, "p50": 200, "p95": 200, "max": 200, "n": 30}
    zero = {"min": 0, "p50": 0, "p95": 0, "max": 0, "n": 30}
    return {
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "instrument": {"pair_id": "2", "pair_from": "EUR", "pair_to": "USD",
                       "category": "forex"},
        "venue_limits": {"max_leverage": row,
                         "overnight_max_leverage": zero}}


def _fixture(tmp_path):
    campaign = "eurusd-d1-alquimia-v4"
    temporal_dir, output = tmp_path / "temporal", tmp_path / "robust"
    costs = _write(tmp_path / "costs.json", _costs())
    methodology = _write(tmp_path / "methodology.json", {})
    temporal = _write(temporal_dir / "04_temporal_validation.json", {
        "stage": "temporal_validation", "decision": "PASS",
        "campaign_id": campaign, "holdout_accessed": False,
        "candidate_ids": ["A"], "candidate_temporal_metrics": {"A": {}},
        "supervised_retest_evidence": {"A": {}},
        "cost_model_path": str(costs), "cost_model_sha256": _sha(costs),
        "methodology_path": str(methodology),
        "methodology_sha256": _sha(methodology)})
    _write(temporal_dir / "temporal_worker_receipt.json", {
        "decision": "PASS_TEMPORAL_VALIDATION", "campaign_id": campaign,
        "candidate_ids": ["A"], "temporal_artifact_path": str(temporal),
        "temporal_artifact_sha256": _sha(temporal)})
    projects = tmp_path / "projects"; projects.mkdir()
    config = _write(tmp_path / "config.json", {
        "base_url": "http://sq", "host_projects_root": str(projects),
        "brokerage_api_max_leverage": 100})
    return temporal_dir, output, config, projects


def test_derives_conservative_forex_limit_without_treating_zero_as_zero_leverage():
    assert venue_max_leverage(_costs()) == 200
    weak = _costs(); weak["venue_limits"]["max_leverage"]["min"] = 100
    assert venue_max_leverage(weak) == 100
    weak["venue_limits"]["overnight_max_leverage"]["p50"] = 50
    with pytest.raises(ValueError, match="EVIDENCE_INSUFFICIENT"):
        venue_max_leverage(weak)


def test_waits_for_temporal_and_terminal_reject_never_runs_sq(tmp_path):
    result = tick(
        temporal_worker_dir=tmp_path / "absent", output_dir=tmp_path / "out",
        worker_config_path=tmp_path / "absent.json")
    assert result["decision"] == "WAITING_FOR_TEMPORAL_VALIDATION"

    temporal, output, config, _ = _fixture(tmp_path)
    receipt = temporal / "temporal_worker_receipt.json"
    value = json.loads(receipt.read_text())
    value.update({"decision": "REJECT_TEMPORAL_VALIDATION", "candidate_ids": []})
    receipt.write_text(json.dumps(value))
    called = []
    result = tick(temporal_worker_dir=temporal, output_dir=output,
                  worker_config_path=config,
                  robustness_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_TEMPORAL_VALIDATION"
    assert called == []


def test_waits_for_foreign_sq_and_runs_then_replays_native_robustness(tmp_path):
    temporal, output, config, projects = _fixture(tmp_path)
    called = []
    waiting = tick(
        temporal_worker_dir=temporal, output_dir=output,
        worker_config_path=config,
        listing_fn=lambda _: [{"projectName": "ACADEMIA", "runningStatus": 1}],
        robustness_fn=lambda **kwargs: called.append(kwargs))
    assert waiting["decision"] == "WAITING_FOR_SQCLI_IDLE"
    assert called == []

    def robustness(**kwargs):
        called.append(kwargs)
        value = {"stage": "robustness", "decision": "PASS",
                 "candidate_ids": ["A"],
                 "evaluated_candidate_robustness_metrics": {"A": {}},
                 "holdout_accessed": False}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(temporal_worker_dir=temporal, output_dir=output,
                  worker_config_path=config, listing_fn=lambda _: [],
                  robustness_fn=robustness)
    first = tick(**common)
    assert first["decision"] == "PASS_ROBUSTNESS"
    assert first["venue_max_leverage"] == 200
    assert first["execution_max_leverage"] == 100
    assert called[0]["execution_max_leverage"] == 100
    assert called[0]["work_dir"] == projects / "ALQ4_RUNTIME/eurusd-d1-alquimia-v4/robustness"
    assert tick(**common) == first
    assert len(called) == 1


def test_exact_checkpointed_mc_project_may_resume(tmp_path):
    temporal, output, config, projects = _fixture(tmp_path)
    work = projects / "ALQ4_RUNTIME/eurusd-d1-alquimia-v4/robustness/t/mc_run"
    _write(work / "retest_preflight.json", {
        "decision": "PASS_RETEST_PREFLIGHT", "project_name": "ALQ4_MC_T"})

    def robustness(**kwargs):
        value = {"decision": "REJECT", "candidate_ids": [],
                 "evaluated_candidate_robustness_metrics": {"A": {}}}
        _write(kwargs["artifact_path"], value)
        return value

    result = tick(
        temporal_worker_dir=temporal, output_dir=output,
        worker_config_path=config,
        listing_fn=lambda _: [{"projectName": "ALQ4_MC_T", "runningStatus": 1}],
        robustness_fn=robustness)
    assert result["decision"] == "REJECT_ROBUSTNESS"
