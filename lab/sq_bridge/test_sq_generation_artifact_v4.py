import hashlib
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

import lab.sq_bridge.sq_generation_artifact_v4 as generation_module
from lab.sq_bridge.sq_generation_artifact_v4 import build_artifact, _validate_project_chain
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest, sq_periods


ROOT = Path(__file__).parent


@pytest.fixture(autouse=True)
def _verified_prerequisite_chain(monkeypatch):
    monkeypatch.setattr(generation_module, "verify_chain", lambda *_: {
        "valid": True, "terminal": False, "next_stage": "sq_generation",
        "promotable": True, "errors": []})


def _fixture(tmp_path, strategy=STRATEGY, settings=SETTINGS):
    databank = tmp_path / "databank"
    databank.mkdir(exist_ok=True)
    sqx = databank / "candidate.sqx"
    with zipfile.ZipFile(sqx, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr("settings.xml", settings)
        archive.writestr("version.txt", "3")
    cfx = tmp_path / "project.cfx"
    config = b'''<Project><Tasks><Task type="Build" name="Build"
      taskXMLFile="Build-Task1.xml" /></Tasks></Project>'''
    task = b'''<Settings><WhatToBuild><BuildMode generationType="genetic-evolution">
      <PopulationSize>25</PopulationSize><MaxGenerations>1</MaxGenerations>
      <Islands>4</Islands><DecimationCoef>1</DecimationCoef>
      <EvoRestartOnFinish status="false" />
      <EvoRestartOnStagnation status="false" />
      </BuildMode></WhatToBuild><Rankings>
      <StopCondition type="databank-full" passedStrategies="100" restartCount="0"
        days="0" hours="0" minutes="0" /></Rankings></Settings>'''
    with zipfile.ZipFile(cfx, "w") as archive:
        archive.writestr("config.xml", config)
        archive.writestr("Build-Task1.xml", task)
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    chain = tmp_path / "chain.json"
    chain.write_text(json.dumps({
        "campaign_id": "campaign-v4", "hypothesis_id": "hypothesis-1",
        "receipts": [{"stage": "market_preflight", "decision": "PASS",
                      "receipt_sha256": "a" * 64},
                     {"stage": "hypothesis_screen", "decision": "PASS",
                      "receipt_sha256": "b" * 64}]}))
    manifest = tmp_path / "project.manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "methodology_id": methodology["methodology_id"],
        "generation_type": "genetic-evolution",
        "attempt_budget": 100,
        "accepted_limit": 100,
        "wall_time_budget_minutes": 0,
        "sq_genetic_shape": {"islands": 4, "population_per_island": 25,
                             "max_generations": 1,
                             "nominal_evaluations": 100},
        "output_sha256": hashlib.sha256(cfx.read_bytes()).hexdigest(),
        "canonical_evaluation_capital": 200,
        "sq_discovery_spread": 0, "sq_discovery_commission": 0,
        "sq_discovery_slippage": 0,
        "venue_cost_application_stage": "post_sq_frozen_cost_model",
        "holdout_sealed": True,
        "source_role": "xml_format_scaffold_only",
        "project_name": "PROJECT_V4",
        "sq_symbol": "NVDA",
        "timeframe": "M15",
        "campaign_id": "campaign-v4",
        "source_hypothesis_id": "hypothesis-1",
        "evidence_chain_path": str(chain),
        "evidence_chain_sha256": hashlib.sha256(chain.read_bytes()).hexdigest(),
        "market_preflight_receipt_sha256": "a" * 64,
        "hypothesis_screen_receipt_sha256": "b" * 64,
    }))
    watchdog = tmp_path / "watchdog-status.json"
    final_log = tmp_path / "watchdog-status.json.sq-final.log"
    final_log.write_text(
        "TASK FINISHED\nStrategies generated: 80, Accepted: 1, Rejected: 79\n")
    watchdog.write_text(json.dumps({
        "project": "PROJECT_V4", "generated": 80,
        "in_databank": 1, "rejected": 79,
        "attempt_counter_source": "sq_project_final_log",
        "sq_final_log_path": str(final_log),
        "sq_final_log_sha256": hashlib.sha256(final_log.read_bytes()).hexdigest(),
        "state": "BUDGET_REACHED", "reason": "ACCEPTED_TARGET",
        "artifacts": [{"path": "candidate.sqx",
                       "sha256": hashlib.sha256(sqx.read_bytes()).hexdigest()}],
    }))
    return databank, cfx, manifest, watchdog


def _build(tmp_path, **overrides):
    databank, cfx, manifest, watchdog = _fixture(
        tmp_path, overrides.pop("strategy", STRATEGY), overrides.pop("settings", SETTINGS))
    params = dict(
        campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
        databank_dir=databank, watchdog_status_path=watchdog,
        project_cfx=cfx, project_manifest_path=manifest,
        methodology_path=ROOT / "methodology_v4.json", output_path=tmp_path / "artifact.json")
    params.update(overrides)
    return build_artifact(**params)


def _rewrite_cfx_task(cfx, old: bytes, new: bytes):
    with zipfile.ZipFile(cfx) as archive:
        config = archive.read("config.xml")
        task = archive.read("Build-Task1.xml").replace(old, new)
    with zipfile.ZipFile(cfx, "w") as archive:
        archive.writestr("config.xml", config)
        archive.writestr("Build-Task1.xml", task)


def test_builds_generation_evidence_from_actual_sqx(tmp_path):
    artifact = _build(tmp_path)
    assert artifact["candidate_ids"] == ["T"]
    assert artifact["rules_per_candidate"] == {"T": 1}
    assert artifact["entry_condition_counts_per_candidate"] == {
        "T": {"long": 1, "short": 1}}
    assert artifact["translation_status_per_candidate"] == {"T": "SUPPORTED_SUBSET"}
    assert artifact["trade_execution_normalized_per_candidate"] == {"T": True}
    assert artifact["stop_loss_required_satisfied_per_candidate"] == {"T": True}
    assert artifact["attempted"] == 80
    assert artifact["databank_candidate_count"] == 1
    assert artifact["sq_config_sha256"] == json.loads(
        (tmp_path / "project.manifest.json").read_text())["output_sha256"]
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(tmp_path / "artifact.json")}
    assert validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native") == []


def test_eurusd_generation_receipt_revalidates_profile_and_exact_period_contract(tmp_path):
    methodology_path = ROOT / "methodology_v4.json"
    source = tmp_path / "source.csv"
    days = [date(2020, 1, 1) + timedelta(days=index) for index in range(200)]
    source.write_text("\n".join(
        f"{day:%Y.%m.%d},00:00,1,1,1,1,1" for day in days) + "\n")
    contract = build_contract(source, methodology_path)
    contract_path = tmp_path / "periods.json"
    contract_path.write_text(json.dumps(contract))
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({"temporal_contract_sha256": digest(contract)}))
    screen = tmp_path / "screen.json"
    screen.write_text(json.dumps({
        "hypothesis_screen_trace_path": str(trace),
        "hypothesis_screen_trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest()}))
    chain = tmp_path / "chain-known.json"
    chain.write_text(json.dumps({
        "campaign_id": "campaign-v4", "hypothesis_id": "d1_breakout",
        "receipts": [
            {"stage": "market_preflight", "decision": "PASS",
             "receipt_sha256": "a" * 64},
            {"stage": "hypothesis_screen", "decision": "PASS",
             "receipt_sha256": "b" * 64, "artifact": str(screen)}]}))
    manifest = {
        "campaign_id": "campaign-v4", "market": "EURUSD",
        "source_hypothesis_id": "d1_breakout",
        "search_profile": "eurusd_d1_breakout_v4",
        "evidence_chain_path": str(chain),
        "evidence_chain_sha256": hashlib.sha256(chain.read_bytes()).hexdigest(),
        "market_preflight_receipt_sha256": "a" * 64,
        "hypothesis_screen_receipt_sha256": "b" * 64,
        "temporal_split_contract_path": str(contract_path),
        "temporal_split_contract_sha256": digest(contract),
        "temporal_source_sha256": contract["source_sha256"],
        "periods": sq_periods(contract),
    }
    assert _validate_project_chain(
        manifest, methodology_path, "campaign-v4", ["d1_breakout"])["sha256"]
    manifest["periods"]["train_to"] = "2099-01-01"
    with pytest.raises(ValueError, match="temporal/perfil"):
        _validate_project_chain(
            manifest, methodology_path, "campaign-v4", ["d1_breakout"])


def test_contract_reopens_sqx_and_rejects_spoofed_rule_count(tmp_path):
    artifact = _build(tmp_path)
    artifact["rules_per_candidate"]["T"] = 2
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(tmp_path / "artifact.json")}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:SQX_CONTRACTS" in errors


def test_rejects_more_rules_than_preregistered(tmp_path):
    predicates = b"".join(b'<Item key="IsRising"><Block><Item key="RSI"/></Block></Item>'
                          for _ in range(4))
    strategy = STRATEGY.replace(
        b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>',
        b'<Item key="AND">' + predicates + b'</Item>', 1)
    with pytest.raises(ValueError, match="Complexitat fora"):
        _build(tmp_path, strategy=strategy)


def test_rejects_unsupported_sqx_instead_of_silently_selecting_it(tmp_path):
    strategy = STRATEGY.replace(b'<Item key="Boolean">', b'<Item key="FutureLeak">', 1)
    with pytest.raises(ValueError, match="SQX no traduible"):
        _build(tmp_path, strategy=strategy)


def test_rejects_sq_candidate_without_protective_stop(tmp_path):
    strategy = STRATEGY.replace(
        b'<Formula key="SQ.Formulas.SLPT.ATRBasedValue"><Param key="#Value#">2</Param><Param key="#AtrPeriod#">14</Param></Formula>',
        b'<Formula key="SQ.Formulas.SLPT.None"/>')
    with pytest.raises(ValueError, match="no executable amb risc controlat"):
        _build(tmp_path, strategy=strategy)


def test_rejects_sq_candidate_with_friday_exit_semantics(tmp_path):
    settings = SETTINGS.replace(
        b'<F key="ExitOnFriday.ExitOnFriday">false</F>',
        b'<F key="ExitOnFriday.ExitOnFriday">true</F>')
    with pytest.raises(ValueError, match="ExitOnFriday"):
        _build(tmp_path, settings=settings)


def test_rejects_tampered_project_config(tmp_path):
    databank, cfx, manifest, watchdog = _fixture(tmp_path)
    cfx.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash del CFX"):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
            databank_dir=databank, watchdog_status_path=watchdog,
            project_cfx=cfx, project_manifest_path=manifest,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")


@pytest.mark.parametrize(("old", "new", "message"), [
    (b'<EvoRestartOnFinish status="false" />',
     b'<EvoRestartOnFinish status="true" />', "RESTARTONFINISH"),
    (b'<MaxGenerations>1</MaxGenerations>',
     b'<MaxGenerations>2</MaxGenerations>', "BUDGET_MISMATCH"),
    (b'<DecimationCoef>1</DecimationCoef>',
     b'<DecimationCoef>2</DecimationCoef>', "DECIMATION"),
])
def test_reopens_hashed_cfx_and_rejects_unsafe_genetic_settings(
        tmp_path, old, new, message):
    databank, cfx, manifest_path, watchdog = _fixture(tmp_path)
    _rewrite_cfx_task(cfx, old, new)
    manifest = json.loads(manifest_path.read_text())
    manifest["output_sha256"] = hashlib.sha256(cfx.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=message):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
            databank_dir=databank, watchdog_status_path=watchdog,
            project_cfx=cfx, project_manifest_path=manifest_path,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")


def test_stage_contract_reopens_cfx_and_rejects_spoofed_shape(tmp_path):
    artifact = _build(tmp_path)
    artifact["sq_genetic_shape"]["nominal_evaluations"] = 99
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False,
               "artifact": str(tmp_path / "artifact.json")}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:CONFIG_CONTRACT" in errors


def test_rejects_databank_changed_after_watchdog_snapshot(tmp_path):
    databank, cfx, manifest, watchdog = _fixture(tmp_path)
    (databank / "candidate.sqx").write_bytes(b"changed-after-stop")
    with pytest.raises(ValueError, match="snapshot final"):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
            databank_dir=databank, watchdog_status_path=watchdog,
            project_cfx=cfx, project_manifest_path=manifest,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")


def test_rejects_watchdog_that_has_not_reached_a_frozen_gate(tmp_path):
    databank, cfx, manifest, watchdog = _fixture(tmp_path)
    status = json.loads(watchdog.read_text())
    status.update({"state": "HEALTHY", "reason": None})
    watchdog.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="gate congelat"):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
            databank_dir=databank, watchdog_status_path=watchdog,
            project_cfx=cfx, project_manifest_path=manifest,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")


def test_rejects_watchdog_without_untampered_exact_final_sq_log(tmp_path):
    databank, cfx, manifest, watchdog = _fixture(tmp_path)
    status = json.loads(watchdog.read_text())
    Path(status["sq_final_log_path"]).write_text(
        "TASK FINISHED\nStrategies generated: 79, Accepted: 1, Rejected: 78\n")
    with pytest.raises(ValueError, match="log final exacte"):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
            databank_dir=databank, watchdog_status_path=watchdog,
            project_cfx=cfx, project_manifest_path=manifest,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")


def test_discovers_nested_strategyquant_databank_paths(tmp_path):
    databank, cfx, manifest, watchdog = _fixture(tmp_path)
    nested = databank / "Results"
    nested.mkdir()
    target = nested / "candidate.sqx"
    (databank / "candidate.sqx").rename(target)
    status = json.loads(watchdog.read_text())
    status["artifacts"] = [{"path": "Results/candidate.sqx",
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}]
    watchdog.write_text(json.dumps(status))
    artifact = build_artifact(
        campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"],
        databank_dir=databank, watchdog_status_path=watchdog,
        project_cfx=cfx, project_manifest_path=manifest,
        methodology_path=ROOT / "methodology_v4.json",
        output_path=tmp_path / "artifact.json")
    assert artifact["candidate_ids"] == ["T"]
    assert artifact["candidate_artifact_paths"]["T"].endswith("Results/candidate.sqx")


def test_chain_rejects_added_sqx_and_spoofed_attempt_count(tmp_path):
    artifact = _build(tmp_path)
    source = tmp_path / "databank/candidate.sqx"
    (tmp_path / "databank/late.sqx").write_bytes(source.read_bytes())
    artifact["attempted"] = 79
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(tmp_path / "artifact.json")}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:DATABANK_INVENTORY" in errors
    assert "STAGE_ARTIFACT:sq_generation:WATCHDOG_CONTRACT" in errors


def test_generation_receipt_detects_tampered_prerequisite_chain(tmp_path):
    artifact = _build(tmp_path)
    manifest = json.loads((tmp_path / "project.manifest.json").read_text())
    chain = __import__("pathlib").Path(manifest["evidence_chain_path"])
    chain.write_text("{}\n")
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(tmp_path / "artifact.json")}
    errors = validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native")
    assert "STAGE_ARTIFACT:sq_generation:PREREQUISITE_CHAIN" in errors
