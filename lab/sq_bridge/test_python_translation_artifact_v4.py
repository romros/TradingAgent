import json
import zipfile
import hashlib

import pytest

from lab.sq_bridge.python_translation_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY


ROOT = __import__("pathlib").Path(__file__).parent


def _sqx(tmp_path):
    path = tmp_path / "candidate.sqx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr("settings.xml", SETTINGS)
        archive.writestr("version.txt", "3")
    return path


def test_builds_self_verifying_translation_artifact_without_holdout(tmp_path):
    artifact_path = tmp_path / "translation.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="T", sqx_path=_sqx(tmp_path),
        ir_path=tmp_path / "candidate.ir.json", artifact_path=artifact_path)
    assert artifact["holdout_accessed"] is False
    assert artifact["translation_exact"] is True
    assert artifact["trade_execution_normalized"] is True
    assert artifact["stop_loss_required_satisfied"] is True
    assert json.loads((tmp_path / "candidate.ir.json").read_text())["strategy_id"] == "T"
    holdout = tmp_path / "holdout.json"
    holdout.write_text(json.dumps({
        "stage": "final_holdout_validation", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["T"],
        "holdout_accessed": True, "holdout_evaluation_count": 1}))
    artifact["final_holdout_artifact_path"] = str(holdout)
    artifact["final_holdout_artifact_sha256"] = hashlib.sha256(
        holdout.read_bytes()).hexdigest()
    artifact_path.write_text(json.dumps(artifact))
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "translation_exact": True,
               "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "python_translation", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_rejects_candidate_id_not_bound_to_sqx(tmp_path):
    with pytest.raises(ValueError, match="lineage mismatch"):
        build_artifact(
            campaign_id="campaign", candidate_id="OTHER", sqx_path=_sqx(tmp_path),
            ir_path=tmp_path / "candidate.ir.json",
            artifact_path=tmp_path / "translation.json")
    assert not (tmp_path / "candidate.ir.json").exists()


def test_rejects_translation_without_protective_stop(tmp_path):
    strategy = STRATEGY.replace(
        b'<Formula key="SQ.Formulas.SLPT.ATRBasedValue"><Param key="#Value#">2</Param><Param key="#AtrPeriod#">14</Param></Formula>',
        b'<Formula key="SQ.Formulas.SLPT.None"/>')
    path = tmp_path / "no-stop.sqx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr("settings.xml", SETTINGS)
        archive.writestr("version.txt", "3")
    with pytest.raises(ValueError, match="Stop loss obligatori"):
        build_artifact(
            campaign_id="campaign", candidate_id="T", sqx_path=path,
            ir_path=tmp_path / "candidate.ir.json",
            artifact_path=tmp_path / "translation.json")
