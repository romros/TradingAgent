import hashlib
import json
import zipfile

import pytest

from lab.sq_bridge.sq_generation_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY


ROOT = __import__("pathlib").Path(__file__).parent


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
        "sq_symbol": "NVDA",
        "timeframe": "M15",
    }))
    return databank, cfx, manifest


def _build(tmp_path, **overrides):
    databank, cfx, manifest = _fixture(
        tmp_path, overrides.pop("strategy", STRATEGY), overrides.pop("settings", SETTINGS))
    params = dict(
        campaign_id="campaign-v4", source_hypothesis_ids=["hypothesis-1"], attempted=80,
        databank_dir=databank, project_cfx=cfx, project_manifest_path=manifest,
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
    assert artifact["sq_config_sha256"] == json.loads(
        (tmp_path / "project.manifest.json").read_text())["output_sha256"]
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(tmp_path / "artifact.json")}
    assert validate_stage_artifact(
        "sq_generation", artifact, receipt, methodology,
        "campaign-v4", "alquimia_native") == []


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
    databank, cfx, manifest = _fixture(tmp_path)
    cfx.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash del CFX"):
        build_artifact(
            campaign_id="campaign-v4", source_hypothesis_ids=["h"], attempted=1,
            databank_dir=databank, project_cfx=cfx, project_manifest_path=manifest,
            methodology_path=ROOT / "methodology_v4.json",
            output_path=tmp_path / "artifact.json")
