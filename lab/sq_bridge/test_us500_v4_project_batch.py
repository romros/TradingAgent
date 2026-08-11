import hashlib
import json
from pathlib import Path

import lab.sq_bridge.eurusd_v4_project_batch as core
import lab.sq_bridge.us500_v4_project_batch as batch
from lab.sq_bridge.temporal_split_contract_v4 import digest


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_us500_batch_uses_us500_market_and_remains_inert(tmp_path, monkeypatch):
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
    hypothesis = "d1_shock_reversion_short"
    plan = tmp_path / "plan.json"
    plan_value = {
        "decision": "PASS_GENERATION_PLAN", "campaign_id": "us500-d1-alquimia-v4",
        "source_hypothesis_id": hypothesis, "chain_hypothesis_id": hypothesis,
        "market": "US500", "project_name": "US500_PROJECT",
        "search_profile": "us500_d1_shock_reversion_v4",
        "generation_type": "genetic-evolution", "attempt_budget": 10_000,
        "accepted_limit": 60, "market_side": "short", "maximum_rules": 3,
        "date_from": "2020-01-01", "date_to": "2021-01-01",
        "periods": {"train_from": "2020-01-01"}, "holdout_sealed": True,
        "screen_artifact_path": str(screen.resolve()),
        "screen_artifact_sha256": _sha(screen),
        "evidence_chain_path": str(chain.resolve()),
        "evidence_chain_sha256": _sha(chain),
        "temporal_split_contract_path": str(periods.resolve()),
        "temporal_split_contract_sha256": digest(contract),
    }
    plan.write_text(json.dumps(plan_value, sort_keys=True))
    bootstrap = tmp_path / "bootstrap.json"
    bootstrap.write_text(json.dumps({
        "decision": "PASS_SQ_BRANCHES_READY",
        "campaign_id": "us500-d1-alquimia-v4",
        "selected_hypothesis_ids": [hypothesis], "sqcli_started": False,
        "branches": {hypothesis: {
            "generation_plan_path": str(plan.resolve()),
            "generation_plan_sha256": _sha(plan),
            "chain_path": str(chain.resolve()), "chain_sha256": _sha(chain),
            "search_profile": "us500_d1_shock_reversion_v4"}},
    }, sort_keys=True))
    calls = []

    def build(**kwargs):
        calls.append(kwargs)
        kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output"].write_bytes(b"us500-cfx")
        manifest = {"project_name": kwargs["project_name"],
                    "attempt_budget": kwargs["attempt_budget"],
                    "search_profile": kwargs["search_profile"],
                    "evidence_chain_sha256": _sha(kwargs["evidence_chain_path"])}
        kwargs["output"].with_suffix(".manifest.json").write_text(json.dumps(manifest))
        return manifest

    shape = {"islands": 4, "population_per_island": 100,
             "max_generations": 25, "nominal_evaluations": 10_000}
    monkeypatch.setattr(core, "build_project", build)
    monkeypatch.setattr(core, "verify_genetic_project", lambda *_: shape)
    monkeypatch.setattr(batch, "compile_plan", lambda **_: plan_value)
    result = batch.compile_projects(
        bootstrap_path=bootstrap, scaffold_path=tmp_path / "scaffold.cfx",
        registry_path=tmp_path / "registry.json",
        methodology_path=tmp_path / "methodology.json",
        output_dir=tmp_path / "out")
    assert result["decision"] == "PASS_CFX_BATCH_READY"
    assert result["sqcli_started"] is False
    assert calls[0]["market_key"] == "US500"
    assert calls[0]["market_side"] == "short"
    assert calls[0]["search_profile"] == "us500_d1_shock_reversion_v4"
