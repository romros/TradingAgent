import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.candle_source_contract_v4 import build as build_candles
from lab.sq_bridge.eurusd_v4_holdout_worker import tick


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return path


def _tick(**kwargs):
    kwargs.setdefault(
        "portfolio_verify_fn", lambda path: json.loads(path.read_text()))
    return tick(**kwargs)


def _fixture(tmp_path, candle_day="2023.06.30"):
    campaign = "eurusd-d1-alquimia-v4"
    small_dir, output = tmp_path / "small", tmp_path / "holdout"
    costs = _write(tmp_path / "costs.json", {})
    methodology = _write(tmp_path / "methodology.json", {})
    split = _write(tmp_path / "split.json", {
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {"final_holdout": {"from": "2023-01-01", "to": "2023-12-31"}}})
    temporal_trace = _write(tmp_path / "temporal.trace.json", {
        "temporal_contract_path": str(split), "temporal_contract_sha256": _sha(split)})
    small_trace = _write(tmp_path / "small.trace.json", {
        "temporal_trace_path": str(temporal_trace),
        "temporal_trace_sha256": _sha(temporal_trace)})
    sizing = _write(small_dir / "06_small_account_economics.json", {
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": campaign, "holdout_accessed": False,
        "candidate_ids": ["A"],
        "cost_model_path": str(costs), "cost_model_sha256": _sha(costs),
        "methodology_path": str(methodology), "methodology_sha256": _sha(methodology),
        "small_account_trace_paths": {"A": str(small_trace)},
        "small_account_trace_sha256": {"A": _sha(small_trace)}})
    portfolio = _write(tmp_path / "portfolio.json", {
        "schema_version": 1, "stage": "portfolio_construction",
        "decision": "PASS", "candidate_ids": ["A", "B", "C", "D"],
        "holdout_accessed": False,
        "source_receipts": {"A": {"campaign_id": campaign,
            "artifact_path": str(sizing), "artifact_sha256": _sha(sizing)}}})
    _write(small_dir / "small_account_worker_receipt.json", {
        "decision": "PASS_SMALL_ACCOUNT", "campaign_id": campaign,
        "candidate_ids": ["A"], "small_account_artifact_path": str(sizing),
        "small_account_artifact_sha256": _sha(sizing)})
    sq = tmp_path / "sq.csv"
    sq.write_text(f"Date,Time,Open,High,Low,Close,Volume\n{candle_day},00:00,1,2,.5,1.5,1\n")
    duka = tmp_path / "duka.csv"; duka.write_bytes(sq.read_bytes())
    contract = _write(tmp_path / "candles.json", build_candles(
        sq_candles_path=sq, sq_timezone="UTC",
        dukascopy_candles_path=duka, dukascopy_timezone="UTC",
        symbol="EURUSD", timeframe="D1"))
    projects = tmp_path / "projects"; projects.mkdir()
    config = _write(tmp_path / "config.json", {
        "base_url": "http://sq", "host_projects_root": str(projects),
        "small_account_candle_contract_path": str(contract),
        "small_account_candle_contract_sha256": _sha(contract),
        "portfolio_artifact_path": str(portfolio)})
    return small_dir, output, config, projects


def test_waits_for_sizing_and_incomplete_candles_do_not_open_holdout(tmp_path):
    result = _tick(
        small_account_worker_dir=tmp_path / "absent", output_dir=tmp_path / "out",
        worker_config_path=tmp_path / "missing")
    assert result["decision"] == "WAITING_FOR_SMALL_ACCOUNT"
    small, output, config, _ = _fixture(tmp_path)
    called = []
    result = _tick(small_account_worker_dir=small, output_dir=output,
                  worker_config_path=config,
                  holdout_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "WAITING_FOR_HOLDOUT_CANDLE_COVERAGE"
    assert result["available_through"] == "2023-06-30"
    assert result["required_through"] == "2023-12-31"
    assert result["holdout_evaluation_count"] == 0
    assert called == []


def test_complete_coverage_opens_once_and_replays_terminal_receipt(tmp_path):
    small, output, config, projects = _fixture(tmp_path, "2023.12.31")
    calls = []

    def holdout(**kwargs):
        calls.append(kwargs)
        value = {"stage": "final_holdout_validation", "decision": "PASS",
                 "candidate_ids": ["A"], "holdout_accessed": True,
                 "holdout_evaluation_count": 1}
        _write(kwargs["artifact_path"], value)
        return value

    common = dict(small_account_worker_dir=small, output_dir=output,
                  worker_config_path=config, listing_fn=lambda _: [],
                  holdout_fn=holdout)
    first = _tick(**common)
    assert first["decision"] == "PASS_FINAL_HOLDOUT"
    assert first["holdout_evaluation_count"] == 1
    assert calls[0]["projects_root"] == projects
    assert _tick(**common) == first
    assert len(calls) == 1


def test_holdout_waits_for_portfolio_and_rejects_foreign_selection(tmp_path):
    small, output, config, _ = _fixture(tmp_path, "2023.12.31")
    config_value = json.loads(config.read_text())
    portfolio = config_value["portfolio_artifact_path"]
    Path(portfolio).unlink()
    result = _tick(small_account_worker_dir=small, output_dir=output,
                  worker_config_path=config)
    assert result["decision"] == "WAITING_FOR_PORTFOLIO_CONSTRUCTION"
    assert result["holdout_accessed"] is False

    sizing = small / "06_small_account_economics.json"
    _write(Path(portfolio), {
        "stage": "portfolio_construction", "decision": "PASS",
        "candidate_ids": ["A", "B", "C", "D"], "holdout_accessed": False,
        "source_receipts": {"A": {"campaign_id": "foreign",
            "artifact_path": str(sizing), "artifact_sha256": _sha(sizing)}}})
    with pytest.raises(ValueError, match="does not authorize"):
        _tick(small_account_worker_dir=small, output_dir=output,
             worker_config_path=config)


def test_foreign_sq_project_blocks_release_and_sizing_reject_is_terminal(tmp_path):
    small, output, config, _ = _fixture(tmp_path, "2023.12.31")
    called = []
    result = _tick(
        small_account_worker_dir=small, output_dir=output,
        worker_config_path=config,
        listing_fn=lambda _: [{"projectName": "ACADEMIA", "runningStatus": 1}],
        holdout_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "WAITING_FOR_SQCLI_IDLE"
    assert result["holdout_evaluation_count"] == 0
    assert called == []

    receipt = small / "small_account_worker_receipt.json"
    value = json.loads(receipt.read_text())
    value.update({"decision": "REJECT_SMALL_ACCOUNT", "candidate_ids": []})
    receipt.write_text(json.dumps(value))
    result = _tick(small_account_worker_dir=small, output_dir=output,
                  worker_config_path=config,
                  holdout_fn=lambda **kwargs: called.append(kwargs))
    assert result["decision"] == "REJECT_SMALL_ACCOUNT"
    assert called == []
