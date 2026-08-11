import json
import hashlib
from datetime import date, timedelta
from pathlib import Path

import pytest

from lab.sq_bridge.hypothesis_screen_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest


ROOT = Path(__file__).parent


def _variant(variant_id, *, wins=30, neighbor_of="central"):
    return {"variant_id": variant_id, "neighbor_of": neighbor_of,
            "market_side": "both",
            "trades": [{"trade_id": f"{variant_id}-trade-{index:02d}",
                        "entry_timestamp": (
                            date(2000, 1, 3) + timedelta(days=index * 2)).isoformat()
                            + "T00:00:00+00:00",
                        "exit_timestamp": (
                            date(2000, 1, 4) + timedelta(days=index * 2)).isoformat()
                            + "T00:00:00+00:00",
                        "gross_return_pct": .5 if index < wins else -.25,
                        "side": "long" if index % 2 == 0 else "short",
                        "holding_days": 1}
                       for index in range(50)]}


def _trace(*, neighbor_wins=(30, 30)):
    return {"schema_version": 1, "trace_type": "hypothesis_screen_grid_trace",
            "train_only": True, "future_periods_accessed": False,
            "holdout_accessed": False, "cost_model_sha256": "",
            "screen_notional_usdc": 200,
            "hypotheses": [{"hypothesis_id": "hypothesis",
                            "market_side": "both",
                            "central_variant_id": "central",
                            "variants": [
                                _variant("central", neighbor_of=None),
                                _variant("neighbor-a", wins=neighbor_wins[0]),
                                _variant("neighbor-b", wins=neighbor_wins[1]),
                            ]}]}


def _cost_model(tmp_path):
    path = tmp_path / "costs.json"
    carry = {scenario + "_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    path.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {"base_roundtrip_bps": 0,
                                  "conservative_roundtrip_bps": 1,
                                  "stress_roundtrip_bps": 2}},
        "carry": {"long": carry, "short": carry}}, sort_keys=True) + "\n")
    return path


def _write(tmp_path, trace, costs):
    source = tmp_path / "canonical.csv"
    rows, day = [], date(2000, 1, 3)
    while len(rows) < 500:
        if day.weekday() < 5:
            rows.append(f"{day:%Y.%m.%d},00:00,1.0,1.1,0.9,1.0,1")
        day += timedelta(days=1)
    source.write_text("\n".join(rows) + "\n")
    lines = source.read_text().splitlines()
    train_rows = len(lines) // 2
    contract = build_contract(source, ROOT / "methodology_v4.json")
    trace.update({
        "source_path": str(source.resolve()),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_rows": len(lines), "train_rows": train_rows,
        "source_first_utc": "2000-01-03T00:00:00+00:00",
        "train_end_utc": lines[train_rows - 1].split(",", 1)[0].replace(".", "-")
            + "T00:00:00+00:00",
        "temporal_split": json.loads((ROOT / "methodology_v4.json").read_text())[
            "temporal_split"],
        "temporal_contract": contract,
        "temporal_contract_sha256": digest(contract),
    })
    trace["cost_model_sha256"] = hashlib.sha256(costs.read_bytes()).hexdigest()
    path = tmp_path / "screen.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_screen_recomputes_grid_pf_neighbors_and_real_contract(tmp_path):
    costs = _cost_model(tmp_path)
    trace = _write(tmp_path, _trace(), costs)
    artifact_path = tmp_path / "screen.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace,
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["attempted"] == 3
    assert artifact["selected_hypothesis_ids"] == ["hypothesis"]
    assert artifact["minimum_selected_stable_neighbors"] == 2
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:hypothesis_screen:TRACE_CONTRACT" in errors
    assert artifact["source_trade_replay_verified"] is False


def test_screen_trace_tampering_is_detected(tmp_path):
    value = _trace()
    costs = _cost_model(tmp_path)
    trace = _write(tmp_path, value, costs)
    artifact_path = tmp_path / "screen.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace,
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    value["hypotheses"][0]["variants"][0]["trades"][0][
        "gross_return_pct"] = -100
    trace.write_text(json.dumps(value))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:hypothesis_screen:TRACE_CONTRACT" in errors


def test_screen_rejects_central_without_two_profitable_neighbors(tmp_path):
    costs = _cost_model(tmp_path)
    artifact = build_artifact(
        campaign_id="campaign", trace_path=_write(
            tmp_path, _trace(neighbor_wins=(10, 30)), costs),
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["selected_hypothesis_ids"] == []


def test_screen_forbids_future_access_and_fake_neighbor_topology(tmp_path):
    costs = _cost_model(tmp_path)
    value = _trace()
    value["future_periods_accessed"] = True
    with pytest.raises(ValueError, match="nomes pot veure train"):
        build_artifact(
            campaign_id="campaign", trace_path=_write(tmp_path, value, costs),
            cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "future.json")
    value = _trace()
    value["hypotheses"][0]["variants"][1]["neighbor_of"] = "someone-else"
    with pytest.raises(ValueError, match="Topologia"):
        build_artifact(
            campaign_id="campaign", trace_path=_write(tmp_path, value, costs),
            cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "neighbors.json")


def test_screen_cost_tampering_and_noncanonical_notional_fail_closed(tmp_path):
    costs = _cost_model(tmp_path)
    trace = _write(tmp_path, _trace(), costs)
    artifact_path = tmp_path / "screen.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_path=trace, cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    costs.write_text("{}\n")
    receipt = {"decision": "PASS", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "hypothesis_screen", artifact, receipt,
        json.loads((ROOT / "methodology_v4.json").read_text()),
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:hypothesis_screen:TRACE_CONTRACT" in errors

    costs = _cost_model(tmp_path)
    value = _trace()
    value["screen_notional_usdc"] = 201
    with pytest.raises(ValueError, match="Nocional canonic"):
        build_artifact(
            campaign_id="campaign", trace_path=_write(tmp_path, value, costs),
            cost_model_path=costs, methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "wrong-notional.json")


def test_screen_rejects_source_tampering_and_trade_after_train(tmp_path):
    costs = _cost_model(tmp_path)
    trace_value = _trace()
    trace = _write(tmp_path, trace_value, costs)
    source = Path(trace_value["source_path"])
    source.write_text(source.read_text() + "2002.01.01,00:00,1,1,1,1,1\n")
    with pytest.raises(ValueError, match="Hash de la font"):
        build_artifact(
            campaign_id="campaign", trace_path=trace, cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "tampered-source.json")

    trace_value = _trace()
    trace_value["hypotheses"][0]["variants"][0]["trades"][0][
        "exit_timestamp"] = "2030-01-01T00:00:00+00:00"
    trace = _write(tmp_path, trace_value, costs)
    with pytest.raises(ValueError, match="fora de train"):
        build_artifact(
            campaign_id="campaign", trace_path=trace, cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "future-trade.json")
