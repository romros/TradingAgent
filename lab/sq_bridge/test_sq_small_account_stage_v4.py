import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.sq_small_account_stage_v4 import run_stage
from lab.sq_bridge.candle_source_contract_v4 import build as build_candle_contract
from lab.sq_bridge.sq_temporal_trace_v4 import derive as derive_temporal
from lab.sq_bridge.test_sq_temporal_trace_v4 import _sources


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    orders, contract, _, receipt = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1";"2020.01.03 10:00:00";"1.01";"100";"-2"',
    ])
    carry = {f"{name}_annual_cost_pct": 0
             for name in ("base", "conservative", "stress")}
    costs = tmp_path / "costs.json"
    costs.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"500": {"base_roundtrip_bps": 0,
                                    "conservative_roundtrip_bps": 1,
                                    "stress_roundtrip_bps": 2}},
        "carry": {"long": carry, "short": carry}}))
    trace = derive_temporal(
        candidate_id="T", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC", retest_receipt_path=receipt)
    trace_path = tmp_path / "temporal.trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    temporal = tmp_path / "04_temporal.json"
    temporal.write_text(json.dumps({
        "stage": "temporal_validation", "campaign_id": "campaign",
        "supervised_retest_evidence": {"T": {
            "temporal_trace_path": str(trace_path),
            "temporal_trace_sha256": _sha(trace_path)}}}))
    robust = tmp_path / "05_robustness.json"
    robust.write_text(json.dumps({
        "stage": "robustness", "decision": "PASS",
        "campaign_id": "campaign", "holdout_accessed": False,
        "candidate_ids": ["T"],
        "candidate_robustness_metrics": {"T": {
            "tested_leverage": 10, "venue_max_leverage": 100}},
        "temporal_validation_artifact_path": str(temporal),
        "temporal_validation_artifact_sha256": _sha(temporal)}))
    candles = tmp_path / "candles.csv"
    candles.write_text("Date,Time,Open,High,Low,Close,Volume\n2020.01.01,00:00,1,1,1,1,1\n")
    dukascopy = tmp_path / "dukascopy.csv"
    dukascopy.write_bytes(candles.read_bytes())
    candle_contract = tmp_path / "candle-contract.json"
    candle_contract.write_text(json.dumps(build_candle_contract(
        sq_candles_path=candles, sq_timezone="UTC",
        dukascopy_candles_path=dukascopy, dukascopy_timezone="UTC",
        symbol="NVDA", timeframe="M15"), indent=2, sort_keys=True) + "\n")
    return robust, costs, candles, candle_contract


def test_orchestrates_per_trade_stop_sizing_for_every_robust_candidate(tmp_path):
    robust, costs, candles, candle_contract = _inputs(tmp_path)
    calls = {"derive": 0, "artifact": 0}
    def derive(**kwargs):
        calls["derive"] += 1
        assert kwargs["venue_max_leverage"] == 100
        assert kwargs["risk_per_trade_pct"] == 1.5
        return {"schema_version": 1, "trace_type": "small_account_trade_trace",
                "source": "synthetic_control", "candidate_id": "T"}
    def artifact(**kwargs):
        calls["artifact"] += 1
        result = {"stage": "small_account_economics", "decision": "PASS",
                  "campaign_id": "campaign", "candidate_ids": ["T"],
                  "holdout_accessed": False}
        kwargs["artifact_path"].write_text(json.dumps(result))
        return result
    result = run_stage(
        campaign_id="campaign", robustness_artifact_path=robust,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        cost_model_path=costs, candles_path=candles,
        candle_contract_path=candle_contract,
        candle_timezone="UTC", work_dir=tmp_path / "work",
        artifact_path=tmp_path / "06_small.json",
        derive_fn=derive, artifact_fn=artifact)
    assert result["candidate_ids"] == ["T"]
    assert result["sizing_semantics"] == \
        "per_trade_risk_budget_over_reconstructed_initial_sq_stop"
    assert result["candles_sha256"] == _sha(candles)
    assert calls == {"derive": 1, "artifact": 1}


def test_stage_rejects_unfrozen_costs(tmp_path):
    robust, costs, candles, candle_contract = _inputs(tmp_path)
    model = json.loads(costs.read_text())
    model["costs_frozen"] = False
    costs.write_text(json.dumps(model))
    with pytest.raises(ValueError, match="FROZEN"):
        run_stage(
            campaign_id="campaign", robustness_artifact_path=robust,
            methodology_path=Path(__file__).with_name("methodology_v4.json"),
            cost_model_path=costs, candles_path=candles,
            candle_contract_path=candle_contract,
            candle_timezone="UTC", work_dir=tmp_path / "work",
            artifact_path=tmp_path / "artifact.json")
