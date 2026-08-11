import hashlib
import json

import pytest

from lab.sq_bridge.eurusd_v4_temporal_worker import tick
from lab.sq_bridge.temporal_split_contract_v4 import digest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def _fixture(tmp_path):
    campaign = "eurusd-d1-alquimia-v4"
    screen_dir = tmp_path / "screen"
    sq_dir = tmp_path / "sq"
    out = tmp_path / "temporal"
    methodology = _write(tmp_path / "methodology.json", {
        "sq_generation": {"accepted_candidates_global_budget": 60}})
    costs = _write(tmp_path / "costs.json", {"decision": "PASS_COSTS_FROZEN"})
    preflight = _write(tmp_path / "preflight.json", {
        "input_receipts": {"costs": {"path": str(costs), "sha256": _sha(costs)}}})
    contract_value = {
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {key: {"from": "2020-01-01", "to": "2020-12-31"}
                     for key in ("train", "validation", "oos", "final_holdout")}}
    contract = _write(tmp_path / "periods.json", contract_value)
    plan = _write(tmp_path / "plan.json", {
        "temporal_split_contract_path": str(contract),
        "temporal_split_contract_sha256": digest(contract_value)})
    bootstrap = _write(tmp_path / "bootstrap.json", {
        "campaign_id": campaign,
        "branches": {"h1": {"generation_plan_path": str(plan),
                              "generation_plan_sha256": _sha(plan)}}})
    _write(screen_dir / "screen_trigger_receipt.json", {
        "decision": "PASS_SCREEN_TRIGGER", "campaign_id": campaign,
        "selected_hypothesis_ids": ["h1"],
        "bootstrap_path": str(bootstrap), "bootstrap_sha256": _sha(bootstrap),
        "frozen_preflight_path": str(preflight),
        "frozen_preflight_sha256": _sha(preflight),
        "methodology_path": str(methodology), "methodology_sha256": _sha(methodology)})
    manifest = _write(tmp_path / "project.manifest.json", {
        "market": "EURUSD", "timeframe": "D1"})
    cfx = tmp_path / "project.cfx"; cfx.write_bytes(b"project")
    _write(sq_dir / "cfx_batch/project_batch.json", {
        "decision": "PASS_CFX_BATCH_READY", "campaign_id": campaign,
        "projects": {"h1": {
            "project_manifest_path": str(manifest),
            "project_manifest_sha256": _sha(manifest),
            "project_cfx_path": str(cfx), "project_cfx_sha256": _sha(cfx)}}})
    universe = _write(sq_dir / "global_sq_generation.json", {
        "stage": "sq_generation", "artifact_role": "global_multi_branch_candidate_universe",
        "decision": "PASS", "campaign_id": campaign, "candidate_ids": ["A"],
        "expected_hypothesis_ids": ["h1"], "source_hypothesis_ids": ["h1"],
        "source_generation_artifacts": {"h1": {"decision": "PASS"}},
        "global_candidate_budget": 60})
    _write(sq_dir / "worker_receipt.json", {
        "decision": "PASS_SQ_GENERATION_ORCHESTRATED", "campaign_id": campaign,
        "candidate_ids": ["A"], "global_generation_artifact_path": str(universe),
        "global_generation_artifact_sha256": _sha(universe)})
    scaffold = tmp_path / "scaffold.cfx"; scaffold.write_bytes(b"scaffold")
    config = _write(tmp_path / "worker_config.json", {
        "scaffold_path": str(scaffold), "scaffold_sha256": _sha(scaffold),
        "base_url": "http://sq", "market": {
            "symbol": "EURUSD", "timeframe": "D1",
            "source_timezone": "Etc/UTC", "ostium_pair_id": "2",
            "ostium_pair_from": "EUR", "ostium_pair_to": "USD",
            "ostium_category": "forex"}})
    return screen_dir, sq_dir, out, config


def test_waits_for_generation_without_touching_other_inputs(tmp_path):
    result = tick(
        screen_dir=tmp_path / "screen", sq_worker_dir=tmp_path / "sq",
        output_dir=tmp_path / "out", worker_config_path=tmp_path / "missing")
    assert result["decision"] == "WAITING_FOR_SQ_GENERATION"


def test_waits_for_foreign_sq_project_and_starts_nothing(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)
    called = []
    result = tick(
        screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
        worker_config_path=config,
        listing_fn=lambda _: [{"projectName": "ACADEMIA", "runningStatus": 1}],
        temporal_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "WAITING_FOR_SQCLI_IDLE"
    assert called == []


def test_runs_global_temporal_stage_and_replays_hashed_receipt(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)
    calls = []

    def temporal(**kwargs):
        calls.append(kwargs)
        value = {"stage": "temporal_validation", "decision": "PASS",
                 "candidate_ids": ["A"],
                 "evaluated_candidate_temporal_metrics": {"A": {}}}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(
        screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
        worker_config_path=config, listing_fn=lambda _: [], temporal_fn=temporal)
    first = tick(**common)
    assert first["decision"] == "PASS_TEMPORAL_VALIDATION"
    assert first["evaluated_candidate_ids"] == ["A"]
    assert calls[0]["symbol"] == "EURUSD"
    assert calls[0]["timeframe"] == "D1"
    assert calls[0]["source_timezone"] == "Etc/UTC"
    assert tick(**common) == first
    assert len(calls) == 1


def test_allows_only_an_exact_checkpointed_retest_to_resume(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)
    _write(out / "retests/token/run/retest_preflight.json", {
        "decision": "PASS_RETEST_PREFLIGHT", "project_name": "ALQ4_RT_TOKEN"})

    def temporal(**kwargs):
        value = {"decision": "REJECT", "candidate_ids": [],
                 "evaluated_candidate_temporal_metrics": {"A": {}}}
        _write(kwargs["artifact_path"], value)
        return value

    result = tick(
        screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
        worker_config_path=config,
        listing_fn=lambda _: [{"projectName": "ALQ4_RT_TOKEN", "runningStatus": 1}],
        temporal_fn=temporal)
    assert result["decision"] == "REJECT_TEMPORAL_VALIDATION"


def test_terminal_empty_sq_generation_never_runs_temporal(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)
    receipt = sq_dir / "worker_receipt.json"
    value = json.loads(receipt.read_text())
    value.update({"decision": "REJECT_NO_SQ_CANDIDATES", "candidate_ids": []})
    receipt.write_text(json.dumps(value))
    called = []
    result = tick(
        screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
        worker_config_path=config, temporal_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_NO_SQ_CANDIDATES"
    assert called == []


def test_rejects_global_universe_not_bound_to_frozen_screen(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)
    universe = sq_dir / "global_sq_generation.json"
    value = json.loads(universe.read_text())
    value["expected_hypothesis_ids"] = ["h2"]
    universe.write_text(json.dumps(value))
    worker = sq_dir / "worker_receipt.json"
    receipt = json.loads(worker.read_text())
    receipt["global_generation_artifact_sha256"] = _sha(universe)
    worker.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="frozen screen/budget"):
        tick(screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
             worker_config_path=config, listing_fn=lambda _: [])


def test_rejects_temporal_result_that_silently_skips_a_global_candidate(tmp_path):
    screen, sq_dir, out, config = _fixture(tmp_path)

    def temporal(**kwargs):
        value = {"decision": "PASS", "candidate_ids": [],
                 "evaluated_candidate_temporal_metrics": {}}
        _write(kwargs["artifact_path"], value)
        return value

    with pytest.raises(ValueError, match="complete SQ universe"):
        tick(screen_dir=screen, sq_worker_dir=sq_dir, output_dir=out,
             worker_config_path=config, listing_fn=lambda _: [],
             temporal_fn=temporal)
