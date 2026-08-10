import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.temporal_validation_artifact_v4 import build_artifact


ROOT = Path(__file__).parent


def _trace(candidate_id: str, *, oos_win: float = 1.0, oos_loss: float = -.5):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    train = [{"trade_id": f"{candidate_id}-train-{index:02d}",
              "exit_timestamp": (start + timedelta(days=index + 1)).isoformat(),
              "net_pnl_usdc": 1.0 if index < 18 else -.5}
             for index in range(30)]
    windows = []
    for window_index in range(3):
        window_start = start + timedelta(days=40 + window_index * 20)
        trades = [{"trade_id": f"{candidate_id}-oos-{window_index}-{index:02d}",
                   "exit_timestamp": (window_start + timedelta(days=index + 1)).isoformat(),
                   "net_pnl_usdc": oos_win if index < 6 else oos_loss}
                  for index in range(10)]
        windows.append({"window_id": f"w{window_index + 1}",
                        "start_utc": window_start.isoformat(),
                        "end_utc": (window_start + timedelta(days=11)).isoformat(),
                        "trades": trades})
    return {"schema_version": 1, "trace_type": "temporal_validation_trade_trace",
            "candidate_id": candidate_id, "capital_usdc": 200,
            "holdout_accessed": False, "cost_scenario": "base",
            "cost_model_sha256": "a" * 64,
            "train_end_utc": (start + timedelta(days=31)).isoformat(),
            "train_trades": train, "oos_windows": windows}


def _write(tmp_path, candidate_id, trace):
    path = tmp_path / f"{candidate_id}.temporal.trace.json"
    path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    return path


def test_temporal_artifact_recomputes_metrics_and_real_trace_contract(tmp_path):
    paths = [_write(tmp_path, "a", _trace("a")),
             _write(tmp_path, "b", _trace("b", oos_win=.8, oos_loss=-.5))]
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=paths,
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
    path = _write(tmp_path, "a", trace)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[path],
        methodology_path=ROOT / "methodology_v4.json", artifact_path=artifact_path)
    trace["oos_windows"][0]["trades"][0]["net_pnl_usdc"] = 100
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
            campaign_id="campaign", trace_paths=[_write(tmp_path, "x", trace)],
            methodology_path=ROOT / "methodology_v4.json",
            artifact_path=tmp_path / "invalid.json")


def test_temporal_artifact_rejects_when_no_candidate_passes_oos(tmp_path):
    trace = _trace("loser", oos_win=.1, oos_loss=-1.0)
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[_write(tmp_path, "loser", trace)],
        methodology_path=ROOT / "methodology_v4.json",
        artifact_path=tmp_path / "reject.json")
    assert artifact["decision"] == "REJECT"
    assert artifact["candidate_ids"] == []
