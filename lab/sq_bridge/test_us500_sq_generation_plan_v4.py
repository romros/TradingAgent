import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import lab.sq_bridge.us500_sq_generation_plan_v4 as planner
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest


ROOT = Path(__file__).parent


def _sources(tmp_path, hypothesis="d1_time_series_momentum_both"):
    source = tmp_path / "source.csv"
    source.write_text("\n".join(
        f"{date(2000, 1, 1) + timedelta(days=index):%Y.%m.%d},00:00,1,1,1,1,1"
        for index in range(1000)) + "\n")
    methodology = ROOT / "methodology_v4.json"
    contract = build_contract(source, methodology)
    trace = tmp_path / "screen.trace.json"
    trace.write_text(json.dumps({
        "temporal_contract": contract,
        "temporal_contract_sha256": digest(contract),
    }, sort_keys=True) + "\n")
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "stage": "hypothesis_screen", "decision": "PASS",
        "campaign_id": "us500-d1-alquimia-v4",
        "selected_hypothesis_ids": [hypothesis],
        "hypothesis_screen_trace_path": str(trace),
        "hypothesis_screen_trace_sha256": hashlib.sha256(
            trace.read_bytes()).hexdigest(),
    }, sort_keys=True) + "\n")
    chain = tmp_path / "chain.json"
    chain.write_text(json.dumps({
        "campaign_id": "us500-d1-alquimia-v4", "hypothesis_id": hypothesis,
        "market": "US500",
        "receipts": [
            {"stage": "market_preflight", "decision": "PASS"},
            {"stage": "hypothesis_screen", "decision": "PASS",
             "artifact": str(screen),
             "artifact_sha256": hashlib.sha256(screen.read_bytes()).hexdigest()},
        ],
    }, sort_keys=True) + "\n")
    return methodology, trace, screen, chain, contract


def _authorized(monkeypatch):
    monkeypatch.setattr(planner, "verify_chain", lambda *_: {
        "valid": True, "terminal": False, "promotable": True,
        "next_stage": "sq_generation"})


def test_compiler_maps_us500_family_direction_periods_and_budget(tmp_path, monkeypatch):
    _authorized(monkeypatch)
    methodology, _, screen, chain, contract = _sources(tmp_path)
    result = planner.compile_plan(
        screen_path=screen, chain_path=chain, methodology_path=methodology,
        period_contract_output=tmp_path / "periods.json",
        plan_output=tmp_path / "plan.json")
    assert result["market"] == "US500"
    assert result["search_profile"] == "us500_d1_time_series_momentum_v4"
    assert result["market_side"] == "both"
    assert result["accepted_limit"] == 60
    assert result["periods"]["train_to"] == contract["segments"]["train"]["to"]
    assert result["project_name"].startswith("ALQUIMIA_US500_D1_V4_")
    assert result["performance_recomputed"] is False


def test_compiler_preserves_short_side_and_splits_global_budget(tmp_path, monkeypatch):
    _authorized(monkeypatch)
    hypothesis = "d1_shock_reversion_short"
    methodology, _, screen, chain, _ = _sources(tmp_path, hypothesis)
    value = json.loads(screen.read_text())
    value["selected_hypothesis_ids"] = [
        "d1_shock_reversion_short", "d1_time_series_momentum_both",
        "d1_volatility_regime_trend_long"]
    screen.write_text(json.dumps(value, sort_keys=True) + "\n")
    value = json.loads(chain.read_text())
    value["receipts"][1]["artifact_sha256"] = hashlib.sha256(
        screen.read_bytes()).hexdigest()
    chain.write_text(json.dumps(value, sort_keys=True) + "\n")
    result = planner.compile_plan(
        screen_path=screen, chain_path=chain, methodology_path=methodology,
        period_contract_output=tmp_path / "periods.json",
        plan_output=tmp_path / "plan.json")
    assert result["search_profile"] == "us500_d1_shock_reversion_v4"
    assert result["market_side"] == "short"
    assert result["accepted_limit"] == 20


def test_compiler_rejects_cross_market_identity(tmp_path, monkeypatch):
    _authorized(monkeypatch)
    methodology, _, screen, chain, _ = _sources(tmp_path)
    value = json.loads(chain.read_text())
    value["market"] = "EURUSD"
    chain.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="identity mismatch"):
        planner.compile_plan(
            screen_path=screen, chain_path=chain, methodology_path=methodology,
            period_contract_output=tmp_path / "periods.json",
            plan_output=tmp_path / "plan.json")
