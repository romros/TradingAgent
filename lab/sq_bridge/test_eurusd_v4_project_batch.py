import hashlib
import json
from pathlib import Path

import pytest

import lab.sq_bridge.eurusd_v4_project_batch as batch
from lab.sq_bridge.temporal_split_contract_v4 import digest


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    for name in ("scaffold.cfx", "registry.json", "methodology.json"):
        (tmp_path / name).write_text(name)
    chain = tmp_path / "chain.json"
    chain.write_text('{"chain":true}\n')
    screen = tmp_path / "screen.json"
    screen.write_text('{"screen":true}\n')
    contract = {"schema_version": 1, "source_first": "2020-01-01",
                "source_last": "2021-01-01"}
    periods = tmp_path / "periods.json"
    periods.write_text(json.dumps(contract))
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({
        "decision": "PASS_GENERATION_PLAN", "campaign_id": "campaign",
        "source_hypothesis_id": "d1_breakout",
        "chain_hypothesis_id": "d1_breakout", "market": "EURUSD",
        "project_name": "PROJECT", "search_profile": "eurusd_d1_breakout_v4",
        "generation_type": "genetic-evolution", "attempt_budget": 10_000,
        "accepted_limit": 64, "market_side": "both",
        "date_from": "2020-01-01", "date_to": "2021-01-01",
        "periods": {"train_from": "2020-01-01"}, "holdout_sealed": True,
        "maximum_rules": 3,
        "screen_artifact_path": str(screen.resolve()),
        "screen_artifact_sha256": _sha(screen),
        "evidence_chain_path": str(chain.resolve()),
        "evidence_chain_sha256": _sha(chain),
        "temporal_split_contract_path": str(periods.resolve()),
        "temporal_split_contract_sha256": digest(contract),
    }, sort_keys=True))
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text(json.dumps({
        "decision": "PASS_SQ_BRANCHES_READY", "campaign_id": "campaign",
        "selected_hypothesis_ids": ["d1_breakout"], "sqcli_started": False,
        "branches": {"d1_breakout": {
            "generation_plan_path": str(plan.resolve()),
            "generation_plan_sha256": _sha(plan),
            "chain_path": str(chain.resolve()), "chain_sha256": _sha(chain),
            "search_profile": "eurusd_d1_breakout_v4"}},
    }, sort_keys=True))
    return bootstrap, plan


def _fake_builder(monkeypatch, plan):
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output"].write_bytes(b"verified-cfx")
        manifest = {
            "project_name": kwargs["project_name"],
            "attempt_budget": kwargs["attempt_budget"],
            "search_profile": kwargs["search_profile"],
            "evidence_chain_sha256": _sha(kwargs["evidence_chain_path"]),
        }
        kwargs["output"].with_suffix(".manifest.json").write_text(json.dumps(manifest))
        return manifest

    shape = {"islands": 4, "population_per_island": 100,
             "max_generations": 25, "nominal_evaluations": 10_000}
    monkeypatch.setattr(batch, "build_project", build)
    monkeypatch.setattr(batch, "verify_genetic_project", lambda *_: shape)
    monkeypatch.setattr(batch, "compile_plan", lambda **_: json.loads(plan.read_text()))
    return calls, shape


def test_compiles_every_authorized_branch_without_starting_sqcli(tmp_path, monkeypatch):
    bootstrap, _ = _inputs(tmp_path)
    plan = tmp_path / "plan.json"
    calls, shape = _fake_builder(monkeypatch, plan)
    result = batch.compile_projects(
        bootstrap_path=bootstrap, scaffold_path=tmp_path / "scaffold.cfx",
        registry_path=tmp_path / "registry.json",
        methodology_path=tmp_path / "methodology.json",
        output_dir=tmp_path / "out")
    assert result["decision"] == "PASS_CFX_BATCH_READY"
    assert result["sqcli_started"] is False
    assert result["projects"]["d1_breakout"]["sq_genetic_shape"] == shape
    assert calls[0]["attempt_budget"] == 10_000
    assert calls[0]["source_hypothesis_id"] == "d1_breakout"
    assert (tmp_path / "out/project_batch.json").is_file()


def test_rejects_tampered_plan_before_building_any_project(tmp_path, monkeypatch):
    bootstrap, plan = _inputs(tmp_path)
    calls, _ = _fake_builder(monkeypatch, plan)
    plan.write_text(plan.read_text() + "\n")
    with pytest.raises(ValueError, match="plan path/hash mismatch"):
        batch.compile_projects(
            bootstrap_path=bootstrap, scaffold_path=tmp_path / "scaffold.cfx",
            registry_path=tmp_path / "registry.json",
            methodology_path=tmp_path / "methodology.json",
            output_dir=tmp_path / "out")
    assert calls == []


def test_rejects_empty_or_nonready_bootstrap(tmp_path):
    bootstrap, _ = _inputs(tmp_path)
    value = json.loads(bootstrap.read_text())
    value["decision"] = "REJECT_NO_HYPOTHESIS"
    bootstrap.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="does not authorize"):
        batch.compile_projects(
            bootstrap_path=bootstrap, scaffold_path=tmp_path / "scaffold.cfx",
            registry_path=tmp_path / "registry.json",
            methodology_path=tmp_path / "methodology.json",
            output_dir=tmp_path / "out")


def test_refuses_to_overwrite_an_existing_project_batch(tmp_path, monkeypatch):
    bootstrap, plan = _inputs(tmp_path)
    calls, _ = _fake_builder(monkeypatch, plan)
    collision = tmp_path / "out/d1_breakout"
    collision.mkdir(parents=True)
    with pytest.raises(ValueError, match="output collision"):
        batch.compile_projects(
            bootstrap_path=bootstrap, scaffold_path=tmp_path / "scaffold.cfx",
            registry_path=tmp_path / "registry.json",
            methodology_path=tmp_path / "methodology.json",
            output_dir=tmp_path / "out")
    assert calls == []
