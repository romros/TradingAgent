import hashlib
import json
import zipfile
from datetime import date, timedelta

import pytest

import lab.sq_bridge.sq_generation_artifact_v4 as generation_module
from lab.sq_bridge.sq_generation_artifact_v4 import build_artifact, _validate_project_chain
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest, sq_periods


ROOT = __import__("pathlib").Path(__file__).parent


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
    cfx.write_bytes(b"frozen-cfx")
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
        "output_sha256": hashlib.sha256(cfx.read_bytes()).hexdigest(),
        "canonical_evaluation_capital": 200,
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
    watchdog.write_text(json.dumps({
        "project": "PROJECT_V4", "generated": 80,
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


def test_builds_generation_evidence_from_actual_sqx(tmp_path):
    artifact = _build(tmp_path)
    assert artifact["candidate_ids"] == ["T"]
    assert artifact["rules_per_candidate"] == {"T": 1}
    assert artifact["entry_condition_counts_per_candidate"] == {
        "T": {"long": 1, "short": 1}}
    assert artifact["translation_status_per_candidate"] == {"T": "SUPPORTED_SUBSET"}
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
