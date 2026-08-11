import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.temporal_validation_artifact_v4 import build_artifact
from lab.sq_bridge.sq_temporal_trace_v4 import derive
from lab.sq_bridge.test_sq_temporal_trace_v4 import _retest_receipt


ROOT = Path(__file__).parent


def _trace(candidate_id: str, *, oos_win: float = 1.0, oos_loss: float = -.5):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    train = [{"trade_id": f"{candidate_id}-train-{index:02d}",
              "exit_timestamp": (start + timedelta(days=index + 1)).isoformat(),
              "gross_return_pct": .5 if index < 18 else -.25,
              "side": "long" if index % 2 == 0 else "short", "holding_days": 1}
             for index in range(30)]
    windows = []
    for window_index, year in enumerate((2021, 2022, 2023)):
        window_start = datetime(year, 2, 1, tzinfo=timezone.utc)
        trades = [{"trade_id": f"{candidate_id}-oos-{window_index}-{index:02d}",
                   "exit_timestamp": (window_start + timedelta(days=index + 1)).isoformat(),
                   "gross_return_pct": (oos_win if index < 6 else oos_loss) / 2,
                   "side": "long" if index % 2 == 0 else "short", "holding_days": 1}
                  for index in range(10)]
        segment = "validation" if year < 2023 else "oos"
        windows.append({"window_id": f"w{window_index + 1:03d}-{segment}-{year}",
                        "start_utc": datetime(year, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "end_utc": datetime(year, 12, 31, 23, 59, 59, 999999,
                                            tzinfo=timezone.utc).isoformat(),
                        "trades": trades})
    return {"schema_version": 1, "trace_type": "temporal_validation_trade_trace",
            "candidate_id": candidate_id, "capital_usdc": 200,
            "holdout_accessed": False, "cost_scenario": "base",
            "cost_model_sha256": "", "evaluation_notional_usdc": 200,
            "train_end_utc": datetime(2020, 12, 31, 23, 59, 59, 999999,
                                      tzinfo=timezone.utc).isoformat(),
            "train_trades": train, "oos_windows": windows}


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


def _write(tmp_path, candidate_id, trace, costs):
    orders = tmp_path / f"{candidate_id}.orders.csv"
    rows = [*trace["train_trades"],
            *(trade for window in trace["oos_windows"] for trade in window["trades"])]
    lines = ['"Ticket";"Type";"Open time";"Open price";"Close time";"Close price"']
    for index, row in enumerate(rows, 1):
        closed = datetime.fromisoformat(row["exit_timestamp"])
        opened = closed - timedelta(days=row["holding_days"])
        entry = 1.0
        sign = 1 if row["side"] == "long" else -1
        exit_price = entry * (1 + sign * row["gross_return_pct"] / 100)
        side = "Buy" if row["side"] == "long" else "Sell"
        lines.append(
            f'"{index}";"{side}";"{opened:%Y.%m.%d %H:%M:%S}";"{entry:.8f}";'
            f'"{closed:%Y.%m.%d %H:%M:%S}";"{exit_price:.8f}"')
    orders.write_text("\n".join(lines) + "\n")
    contract = tmp_path / f"{candidate_id}.temporal-contract.json"
    contract.write_text(json.dumps({
        "schema_version": 1,
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2019-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-01", "to": "2022-12-31"},
            "oos": {"from": "2023-01-01", "to": "2023-12-31"},
            "final_holdout": {"from": "2024-01-01", "to": "2024-12-31"},
        },
    }, sort_keys=True) + "\n")
    derived = derive(
        candidate_id=candidate_id, orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC",
        retest_receipt_path=_retest_receipt(
            tmp_path, orders, candidate_id=candidate_id))
    for key in ("holdout_accessed", "evaluation_notional_usdc"):
        if trace.get(key) != derived.get(key):
            derived[key] = trace[key]
    path = tmp_path / f"{candidate_id}.temporal.trace.json"
    path.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n")
    return path


def test_temporal_artifact_recomputes_metrics_and_real_trace_contract(tmp_path):
    costs = _cost_model(tmp_path)
    paths = [_write(tmp_path, "a", _trace("a"), costs),
             _write(tmp_path, "b", _trace("b", oos_win=.8, oos_loss=-.5), costs)]
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=paths,
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    assert artifact["candidate_ids"] == ["a"]
    assert set(artifact["evaluated_candidate_temporal_metrics"]) == {"a", "b"}
    receipt = {"decision": "PASS", "candidate_ids": ["a"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    assert validate_stage_artifact(
        "temporal_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_temporal_trace_tampering_or_holdout_access_fails_closed(tmp_path):
    trace = _trace("a")
    costs = _cost_model(tmp_path)
    path = _write(tmp_path, "a", trace, costs)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[path],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    trace["oos_windows"][0]["trades"][0]["gross_return_pct"] = 100
    path.write_text(json.dumps(trace))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["a"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "temporal_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:temporal_validation:TRACE_CONTRACT" in errors

    trace = _trace("x")
    trace["holdout_accessed"] = True
    with pytest.raises(ValueError, match="sense obrir holdout"):
        build_artifact(
            campaign_id="campaign", trace_paths=[_write(tmp_path, "x", trace, costs)],
            cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "invalid.json")


def test_valid_zero_trade_candidate_is_recorded_as_temporal_reject(tmp_path):
    trace = _trace("zero")
    trace["train_trades"] = []
    for window in trace["oos_windows"]:
        window["trades"] = []
    costs = _cost_model(tmp_path)
    trace_path = _write(tmp_path, "zero", trace, costs)
    artifact_path = tmp_path / "artifact-zero.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=artifact_path)
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []
    metrics = artifact["evaluated_candidate_temporal_metrics"]["zero"]
    assert metrics["oos_trades"] == 0
    assert metrics["oos_profit_factor"] == 0
    assert metrics["temporal_eligibility_failure"] == "NO_TRAIN_TRADES"
    receipt = {"decision": "REJECT", "candidate_ids": [],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    assert validate_stage_artifact(
        "temporal_validation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_non_positive_train_expectancy_is_evidence_not_pipeline_error(tmp_path):
    trace = _trace("negative")
    for trade in trace["train_trades"]:
        trade["gross_return_pct"] = -0.1
    costs = _cost_model(tmp_path)
    path = _write(tmp_path, "negative", trace, costs)
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[path], cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "negative-artifact.json")
    metrics = artifact["evaluated_candidate_temporal_metrics"]["negative"]
    assert artifact["decision"] == "REJECT"
    assert metrics["temporal_eligibility_failure"] == "NON_POSITIVE_TRAIN_EXPECTANCY"
    assert metrics["train_oos_expectancy_decay_pct"] == 1_000_000


def test_temporal_artifact_rejects_when_no_candidate_passes_oos(tmp_path):
    costs = _cost_model(tmp_path)
    trace = _trace("loser", oos_win=.1, oos_loss=-1.0)
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, "loser", trace, costs)],
        cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []


def test_temporal_cost_tampering_and_noncanonical_notional_fail_closed(tmp_path):
    costs = _cost_model(tmp_path)
    path = _write(tmp_path, "a", _trace("a"), costs)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[path], cost_model_path=costs,
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    costs.write_text("{}\n")
    receipt = {"decision": "PASS", "candidate_ids": ["a"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "temporal_validation", artifact, receipt,
        json.loads((ROOT / "methodology_v4.json").read_text()),
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:temporal_validation:TRACE_CONTRACT" in errors

    costs = _cost_model(tmp_path)
    trace = _trace("x")
    trace["evaluation_notional_usdc"] = 201
    with pytest.raises(ValueError, match="Nocional temporal canonic"):
        build_artifact(
            campaign_id="campaign",
            trace_paths=[_write(tmp_path, "x", trace, costs)],
            cost_model_path=costs, methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "wrong-notional.json")
