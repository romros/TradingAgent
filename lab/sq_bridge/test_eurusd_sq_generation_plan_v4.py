import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

import lab.sq_bridge.eurusd_sq_generation_plan_v4 as planner
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest


ROOT = Path(__file__).parent


def _sources(tmp_path, hypothesis="d1_breakout"):
    source, rows = tmp_path / "source.csv", []
    for index in range(1000):
        day = date(2000, 1, 1) + timedelta(days=index)
        rows.append(f"{day:%Y.%m.%d},00:00,1,1,1,1,1")
    source.write_text("\n".join(rows) + "\n")
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
        "campaign_id": "campaign", "selected_hypothesis_ids": [hypothesis],
        "hypothesis_screen_trace_path": str(trace),
        "hypothesis_screen_trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
    }, sort_keys=True) + "\n")
    chain = tmp_path / "chain.json"
    chain.write_text(json.dumps({
        "campaign_id": "campaign", "hypothesis_id": hypothesis,
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


def test_compiler_maps_screened_family_to_exact_sq_profile_and_periods(tmp_path, monkeypatch):
    _authorized(monkeypatch)
    methodology, _, screen, chain, contract = _sources(tmp_path)
    result = planner.compile_plan(
        screen_path=screen, chain_path=chain, methodology_path=methodology,
        period_contract_output=tmp_path / "periods.json",
        plan_output=tmp_path / "plan.json")
    assert result["decision"] == "PASS_GENERATION_PLAN"
    assert result["search_profile"] == "eurusd_d1_breakout_v4"
    assert result["generation_type"] == "genetic-evolution"
    assert result["attempt_budget"] == 10_000
    assert result["periods"]["train_to"] == contract["segments"]["train"]["to"]
    assert result["periods"]["holdout_from"] == contract[
        "segments"]["final_holdout"]["from"]
    assert result["alquimia_project_arguments"]["period_contract"] == str(
        (tmp_path / "periods.json").resolve())
    assert result["performance_recomputed"] is False


def test_compiler_rejects_unscreened_family_and_trace_tampering(tmp_path, monkeypatch):
    _authorized(monkeypatch)
    methodology, trace, screen, chain, _ = _sources(tmp_path)
    value = json.loads(chain.read_text())
    value["hypothesis_id"] = "d1_momentum"
    chain.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="did not pass"):
        planner.compile_plan(
            screen_path=screen, chain_path=chain, methodology_path=methodology,
            period_contract_output=tmp_path / "periods.json",
            plan_output=tmp_path / "plan.json")

    methodology, trace, screen, chain, _ = _sources(tmp_path)
    trace.write_text("{}\n")
    with pytest.raises(ValueError, match="trace hash"):
        planner.compile_plan(
            screen_path=screen, chain_path=chain, methodology_path=methodology,
            period_contract_output=tmp_path / "periods.json",
            plan_output=tmp_path / "plan.json")
