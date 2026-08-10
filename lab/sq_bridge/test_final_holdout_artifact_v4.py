import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.final_holdout_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _trace(*, evaluation_count=1, stress_scale=1.0):
    trades = []
    for index in range(20):
        win = index < 12
        trades.append({
            "trade_id": f"t{index:02d}",
            "net_pnl_usdc_by_cost": {
                "base": 1.0 if win else -.3,
                "conservative": .8 if win else -.4,
                "stress": (.7 if win else -.5) * stress_scale,
            },
        })
    return {
        "schema_version": 1, "trace_type": "final_holdout_trade_trace",
        "candidate_id": "candidate", "capital_usdc": 200,
        "selection_frozen_before_holdout": True,
        "parameters_changed_after_holdout": False,
        "holdout_evaluation_count": evaluation_count,
        "trades": trades,
    }


def _build(tmp_path, trace=None):
    trace_path = tmp_path / "holdout.trace.json"
    trace_path.write_text(json.dumps(trace or _trace(), indent=2, sort_keys=True) + "\n")
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", trace_path=trace_path,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    return artifact, artifact_path


def test_holdout_pass_is_recomputed_from_twenty_trade_cost_trace(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    assert artifact["decision"] == "PASS"
    assert artifact["holdout_trades"] == 20
    assert artifact["minimum_holdout_profit_factor"] > 1.1
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_second_holdout_evaluation_is_forbidden(tmp_path):
    with pytest.raises(ValueError, match="una vegada"):
        _build(tmp_path, _trace(evaluation_count=2))


def test_losing_stress_scenario_rejects_whole_candidate(tmp_path):
    trace = _trace()
    for row in trace["trades"]:
        row["net_pnl_usdc_by_cost"]["stress"] -= 1.0
    artifact, _ = _build(tmp_path, trace)
    assert artifact["decision"] == "REJECT"
    assert artifact["minimum_holdout_net_expectancy_usdc"] < .1


def test_hashed_but_tampered_summary_does_not_pass_recomputation(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    artifact["minimum_holdout_profit_factor"] += 1
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": True, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "final_holdout_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:final_holdout_validation:TRACE_CONTRACT" in errors
    assert "STAGE_ARTIFACT:final_holdout_validation:PROFIT_FACTOR_RECOMPUTES" in errors
