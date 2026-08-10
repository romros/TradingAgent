import json
from pathlib import Path

from lab.sq_bridge.e2e_control import generate, payload
from lab.sq_bridge.methodology import validate
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent
METHODOLOGY_PATH = ROOT / "methodology_v4.json"
METHODOLOGY = json.loads(METHODOLOGY_PATH.read_text())


def test_v4_separates_pre_sq_screen_from_strategyquant_generation():
    assert validate(METHODOLOGY) == []
    assert METHODOLOGY["stages"][:3] == [
        "market_preflight", "hypothesis_screen", "sq_generation"]
    assert METHODOLOGY["market_preflight"][
        "minimum_overall_observation_coverage_ratio"] == .9
    assert METHODOLOGY["market_preflight"]["performance_accessed"] is False


def test_v4_market_preflight_cannot_pass_on_mapping_without_history():
    artifact = payload("market_preflight", [], False)
    artifact.update({"campaign_id": "v4", "historical_coverage_pass": False,
                     "historical_overall_coverage_ratio": .42,
                     "historical_minimum_period_coverage_ratio": .02})
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "market_preflight", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:market_preflight:HISTORICAL_COVERAGE_PASS" in errors
    assert "STAGE_ARTIFACT:market_preflight:OVERALL_COVERAGE" in errors
    assert "STAGE_ARTIFACT:market_preflight:PERIOD_COVERAGE" in errors


def test_v4_recomputes_coverage_instead_of_trusting_reported_summary():
    artifact = payload("market_preflight", [], False)
    artifact["campaign_id"] = "v4"
    artifact["historical_overall_coverage_ratio"] = .99
    artifact["historical_minimum_period_coverage_ratio"] = .99
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    errors = validate_stage_artifact(
        "market_preflight", artifact, receipt, METHODOLOGY, "v4", "alquimia_native")
    assert "STAGE_ARTIFACT:market_preflight:OVERALL_RECOMPUTES" in errors
    assert "STAGE_ARTIFACT:market_preflight:PERIOD_MINIMUM_RECOMPUTES" in errors


def test_v4_full_control_wires_nine_stages_without_becoming_promotable(tmp_path):
    result = generate(METHODOLOGY_PATH, tmp_path)
    assert result["valid"] is True
    assert result["operational_control_complete"] is True
    assert result["paper_ready"] is False
    assert len(list(tmp_path.glob("[0-9][0-9]_*.json"))) == 9
