import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.sq_temporal_stage_v4 import run_stage
from lab.sq_bridge.test_alquimia_retest import _fixture


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    template, candidate, discovery = _fixture(source_dir)
    generation = tmp_path / "03_sq_generation.json"
    generation.write_text(json.dumps({
        "stage": "sq_generation", "decision": "PASS",
        "campaign_id": "campaign", "holdout_accessed": False,
        "candidate_ids": ["T"],
        "candidate_artifact_paths": {"T": str(candidate)},
        "candidate_artifact_hashes": {"T": _sha(candidate)},
    }))
    temporal = tmp_path / "temporal.json"
    temporal.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2017-01-01", "to": "2021-12-31"},
            "validation": {"from": "2022-01-01", "to": "2023-12-31"},
            "oos": {"from": "2024-01-01", "to": "2025-07-31"},
            "final_holdout": {"from": "2025-08-01", "to": "2026-07-31"},
        },
    }))
    costs = tmp_path / "costs.json"
    costs.write_text('{"decision":"PASS_COSTS_FROZEN"}\n')
    return template, candidate, discovery, generation, temporal, costs


def test_stage_orchestrates_each_candidate_and_reuses_retest_cfx_checkpoint(tmp_path):
    template, _candidate, discovery, generation, temporal, costs = _inputs(tmp_path)
    calls = {"retest": 0, "derive": 0, "artifact": 0}

    def retest(**kwargs):
        calls["retest"] += 1
        output = kwargs["output_dir"]
        output.mkdir(parents=True, exist_ok=True)
        orders = output / "orders.csv"
        orders.write_text("observed\n")
        receipt = {
            "decision": "PASS_SUPERVISED_RETEST", "candidate_id": "T",
            "holdout_accessed": False, "orders_csv_path": str(orders),
        }
        (output / "supervised_retest_receipt.json").write_text(json.dumps(receipt))
        return receipt

    def derive(**kwargs):
        calls["derive"] += 1
        assert kwargs["temporal_contract_path"] == temporal
        assert kwargs["retest_receipt_path"].is_file()
        return {"source": "strategyquant_orders_export", "candidate_id": "T"}

    def artifact(**kwargs):
        calls["artifact"] += 1
        value = {"stage": "temporal_validation", "campaign_id": "campaign",
                 "decision": "PASS", "candidate_ids": ["T"],
                 "holdout_accessed": False}
        kwargs["artifact_path"].write_text(json.dumps(value))
        return value

    params = dict(
        campaign_id="campaign", generation_artifact_path=generation,
        retest_template_path=template, discovery_manifest_path=discovery,
        temporal_contract_path=temporal,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        cost_model_path=costs, symbol="NVDA", timeframe="M15",
        source_timezone="UTC", work_dir=tmp_path / "work",
        artifact_path=tmp_path / "04_temporal_validation.json",
        retest_fn=retest, derive_fn=derive, artifact_fn=artifact)
    first = run_stage(**params)
    cfx = next((tmp_path / "work").glob("*/pre_holdout.cfx"))
    first_hash = _sha(cfx)
    second = run_stage(**params)
    assert first["decision"] == second["decision"] == "PASS"
    assert _sha(cfx) == first_hash
    assert calls == {"retest": 2, "derive": 2, "artifact": 2}
    assert first["supervised_retest_evidence"]["T"][
        "supervised_retest_receipt_sha256"]


def test_stage_rejects_generation_candidate_hash_or_identity_mismatch(tmp_path):
    template, candidate, discovery, generation, temporal, costs = _inputs(tmp_path)
    value = json.loads(generation.read_text())
    value["candidate_artifact_hashes"]["T"] = "0" * 64
    generation.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="path/hash mismatch"):
        run_stage(
            campaign_id="campaign", generation_artifact_path=generation,
            retest_template_path=template, discovery_manifest_path=discovery,
            temporal_contract_path=temporal,
            methodology_path=Path(__file__).with_name("methodology_v4.json"),
            cost_model_path=costs, symbol="NVDA", timeframe="M15",
            source_timezone="UTC", work_dir=tmp_path / "work",
            artifact_path=tmp_path / "artifact.json")
