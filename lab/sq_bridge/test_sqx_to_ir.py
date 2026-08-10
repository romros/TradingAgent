import json
import zipfile

import pytest

from lab.sq_bridge.sqx_to_ir import translate
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY


def _sqx(tmp_path, strategy=STRATEGY):
    path = tmp_path / "candidate.sqx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr("settings.xml", SETTINGS)
        archive.writestr("version.txt", "3")
    return path


def test_translation_is_canonical_and_bound_to_source(tmp_path):
    source = _sqx(tmp_path)
    first = tmp_path / "first.ir.json"
    second = tmp_path / "second.ir.json"
    result = translate(source, first)
    translate(source, second)
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text()) == result
    assert result["ir_type"] == "alquimia_strategy_ir"
    assert result["translation_semantics"] == "exact_supported_subset"
    assert result["strategy_id"] == "T"
    assert result["source_sqx_sha256"]
    assert result["entries"]["long"]["signal"]["op"] == "Boolean"


def test_translation_rejects_operator_outside_supported_subset(tmp_path):
    strategy = STRATEGY.replace(b'<Item key="Boolean">', b'<Item key="FutureLeak">', 1)
    with pytest.raises(ValueError, match="fora del subset"):
        translate(_sqx(tmp_path, strategy), tmp_path / "candidate.ir.json")


def test_v4_contract_recomputes_ir_and_rejects_arbitrary_hashed_json(tmp_path):
    source = _sqx(tmp_path)
    ir = tmp_path / "candidate.ir.json"
    translate(source, ir)
    import hashlib
    methodology = json.loads((__import__("pathlib").Path(__file__).parent
                              / "methodology_v4.json").read_text())
    artifact = {
        "schema_version": 1, "stage": "python_translation",
        "campaign_id": "campaign", "decision": "PASS", "candidate_ids": ["T"],
        "holdout_accessed": False, "evidence_class": "observed",
        "translation_exact": True, "supported_subset": True,
        "sqx_path": source.name,
        "sqx_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "canonical_ir_path": ir.name,
        "canonical_ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest(),
    }
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "translation_exact": True,
               "artifact": str(tmp_path / "artifact.json")}
    assert validate_stage_artifact(
        "python_translation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []
    ir.write_text('{"arbitrary": true}\n')
    artifact["canonical_ir_sha256"] = hashlib.sha256(ir.read_bytes()).hexdigest()
    errors = validate_stage_artifact(
        "python_translation", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:python_translation:CANONICAL_IR" in errors
