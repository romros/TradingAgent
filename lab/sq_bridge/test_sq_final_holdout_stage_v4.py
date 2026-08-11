import hashlib
import json
from pathlib import Path

import pytest

import lab.sq_bridge.sq_final_holdout_stage_v4 as module


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    costs = tmp_path / "costs.json"; costs.write_text("{}")
    source_cfx = tmp_path / "pre.cfx"; source_cfx.write_bytes(b"cfx")
    pre_receipt = tmp_path / "pre-receipt.json"
    pre_receipt.write_text(json.dumps({
        "source_cfx_path": str(source_cfx), "source_cfx_sha256": _sha(source_cfx)}))
    temporal = tmp_path / "temporal.json"
    temporal.write_text(json.dumps({
        "supervised_retest_receipt_path": str(pre_receipt),
        "supervised_retest_receipt_sha256": _sha(pre_receipt)}))
    sqx = tmp_path / "candidate.sqx"; sqx.write_bytes(b"sqx")
    small_trace = tmp_path / "small.trace.json"
    small_trace.write_text(json.dumps({
        "source_sqx_path": str(sqx), "source_sqx_sha256": _sha(sqx),
        "temporal_trace_path": str(temporal), "temporal_trace_sha256": _sha(temporal)}))
    sizing = tmp_path / "small.json"
    sizing.write_text(json.dumps({
        "stage": "small_account_economics", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["T"],
        "holdout_accessed": False, "cost_model_sha256": _sha(costs),
        "small_account_trace_paths": {"T": str(small_trace)},
        "small_account_trace_sha256": {"T": _sha(small_trace)}}))
    split = tmp_path / "split.json"
    split.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-01", "to": "2021-12-31"},
            "oos": {"from": "2022-01-01", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-01", "to": "2023-12-31"}}}))
    candles = tmp_path / "candles.csv"; candles.write_text("candles")
    candle_contract = tmp_path / "candle.json"
    candle_contract.write_text(json.dumps({
        "symbol": "NVDA", "timeframe": "M15", "decision": "PASS_CANDLE_PARITY",
        "last_common_timestamp_utc": "2023-12-31T00:00:00+00:00"}))
    return costs, sizing, split, candles, candle_contract


def test_orchestrates_exactly_one_native_uncensored_holdout(tmp_path, monkeypatch):
    costs, sizing, split, candles, candle_contract = _inputs(tmp_path)
    monkeypatch.setattr(module, "rebuild_small", lambda value: value)
    monkeypatch.setattr(module, "verify_candle_contract", lambda value: value)
    calls = {"generate": 0, "supervise": 0, "derive": 0, "artifact": 0}

    def generate(**kwargs):
        calls["generate"] += 1
        assert kwargs["stage"] == "holdout"
        assert kwargs["holdout_release_artifact"] == sizing.resolve()
        kwargs["output"].write_bytes(b"holdout-cfx")
        kwargs["output"].with_suffix(".manifest.json").write_text("{}")
        return {"performance_filters_applied_in_sq": False}

    def supervise(**kwargs):
        calls["supervise"] += 1
        output = kwargs["output_dir"]
        output.mkdir(parents=True)
        orders = output / "orders.csv"; orders.write_text("orders")
        receipt = {"holdout_accessed": True, "holdout_evaluation_count": 1,
                   "orders_csv_path": str(orders)}
        (output / "supervised_retest_receipt.json").write_text(json.dumps(receipt))
        return receipt

    def derive(**kwargs):
        calls["derive"] += 1
        return {"schema_version": 2, "trace_type": "final_holdout_trade_trace"}

    def artifact(**kwargs):
        calls["artifact"] += 1
        result = {"stage": "final_holdout_validation", "decision": "PASS",
                  "campaign_id": "campaign", "candidate_ids": ["T"],
                  "holdout_accessed": True}
        kwargs["artifact_path"].write_text(json.dumps(result))
        return result

    result = module.run_stage(
        campaign_id="campaign", small_account_artifact_path=sizing,
        temporal_contract_path=split, cost_model_path=costs,
        candles_path=candles, candle_timezone="UTC",
        candle_contract_path=candle_contract, source_timezone="UTC",
        work_dir=tmp_path / "work", projects_root=tmp_path / "projects",
        artifact_path=tmp_path / "artifact.json",
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        generate_fn=generate, supervise_fn=supervise,
        derive_fn=derive, artifact_fn=artifact)
    assert result["native_sq_uncensored"] is True
    assert calls == {"generate": 1, "supervise": 1, "derive": 1, "artifact": 1}


def test_release_intent_cannot_change_after_being_written(tmp_path, monkeypatch):
    costs, sizing, split, candles, candle_contract = _inputs(tmp_path)
    monkeypatch.setattr(module, "rebuild_small", lambda value: value)
    monkeypatch.setattr(module, "verify_candle_contract", lambda value: value)
    candidate_dir = tmp_path / "work" / hashlib.sha256(b"T").hexdigest()[:16]
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "holdout-release-manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="INTENT_MISMATCH"):
        module.run_stage(
            campaign_id="campaign", small_account_artifact_path=sizing,
            temporal_contract_path=split, cost_model_path=costs,
            candles_path=candles, candle_timezone="UTC",
            candle_contract_path=candle_contract, source_timezone="UTC",
            work_dir=tmp_path / "work", projects_root=tmp_path / "projects",
            artifact_path=tmp_path / "artifact.json",
            methodology_path=Path(__file__).with_name("methodology_v4.json"))
