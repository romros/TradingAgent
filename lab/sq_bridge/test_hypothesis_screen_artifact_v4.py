import json
from pathlib import Path

import pytest

from lab.sq_bridge.hypothesis_screen_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _variant(variant_id, *, wins=30, neighbor_of="central"):
    return {"variant_id": variant_id, "neighbor_of": neighbor_of,
            "trades": [{"trade_id": f"{variant_id}-trade-{index:02d}",
                        "net_pnl_usdc_by_cost": {
                            "base": 1.0 if index < wins else -.5,
                            "conservative": .8 if index < wins else -.5,
                            "stress": .7 if index < wins else -.5}}
                       for index in range(50)]}


def _trace(*, neighbor_wins=(30, 30)):
    return {"schema_version": 1, "trace_type": "hypothesis_screen_grid_trace",
            "train_only": True, "future_periods_accessed": False,
            "holdout_accessed": False, "cost_model_sha256": "a" * 64,
            "hypotheses": [{"hypothesis_id": "hypothesis",
                            "central_variant_id": "central",
                            "variants": [
                                _variant("central", neighbor_of=None),
                                _variant("neighbor-a", wins=neighbor_wins[0]),
                                _variant("neighbor-b", wins=neighbor_wins[1]),
                            ]}]}


def _write(tmp_path, trace):
    path = tmp_path / "screen.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_screen_recomputes_grid_pf_neighbors_and_real_contract(tmp_path):
    trace = _write(tmp_path, _trace())
    artifact_path = tmp_path / "screen.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["attempted"] == 3
    assert artifact["selected_hypothesis_ids"] == ["hypothesis"]
    assert artifact["minimum_selected_stable_neighbors"] == 2
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_screen_trace_tampering_is_detected(tmp_path):
    value = _trace()
    trace = _write(tmp_path, value)
    artifact_path = tmp_path / "screen.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    value["hypotheses"][0]["variants"][0]["trades"][0][
        "net_pnl_usdc_by_cost"]["stress"] = -100
    trace.write_text(json.dumps(value))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:hypothesis_screen:TRACE_CONTRACT" in errors


def test_screen_rejects_central_without_two_profitable_neighbors(tmp_path):
    artifact = build_artifact(
        campaign_id="campaign", trace_path=_write(tmp_path, _trace(neighbor_wins=(10, 30))),
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["selected_hypothesis_ids"] == []


def test_screen_forbids_future_access_and_fake_neighbor_topology(tmp_path):
    value = _trace()
    value["future_periods_accessed"] = True
    with pytest.raises(ValueError, match="nomes pot veure train"):
        build_artifact(
            campaign_id="campaign", trace_path=_write(tmp_path, value),
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "future.json")
    value = _trace()
    value["hypotheses"][0]["variants"][1]["neighbor_of"] = "someone-else"
    with pytest.raises(ValueError, match="Topologia"):
        build_artifact(
            campaign_id="campaign", trace_path=_write(tmp_path, value),
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "neighbors.json")
