import json
from pathlib import Path

from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.us500_d1_market_preflight_v4 import compose


ROOT = Path(__file__).parent
METHODOLOGY = json.loads((ROOT / "methodology_v4.json").read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value))


def fixture(tmp_path: Path, *, measured: bool) -> Path:
    write(tmp_path / "coverage.json", {
        "decision": "PASS_HISTORICAL_COVERAGE", "performance_accessed": False,
        "historical_coverage_pass": True, "historical_expected_observations": 100,
        "historical_complete_observations": 95, "historical_overall_coverage_ratio": .95,
        "historical_minimum_period_coverage_ratio": .85,
        "historical_period_coverage": {"a": .85, "b": .95}})
    write(tmp_path / "mapping.json", {
        "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False,
        "common_complete_session_coverage_ratio": .97,
        "d1_close_return_correlation": .999})
    write(tmp_path / "vix.json", {
        "decision": "PASS_VIX_DATA_TIMING", "spx_performance_accessed": False,
        "strategy_rule_defined": False,
        "timing_policy": {"same_session_use_allowed": False,
                          "earliest_use": "next US500 session"}})
    if measured:
        write(tmp_path / "costs.json", {
            "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
            "by_notional": {"200": {"base_roundtrip_bps": 3}},
            "paper_authorized": False, "live_authorized": False})
    config = tmp_path / "config.json"
    write(config, {"schema_version": 1, "campaign_id": "us500-test",
                   "ostium_pair_id": "SPX/USD", "coverage": "coverage.json",
                   "mapping": "mapping.json", "vix": "vix.json", "costs": "costs.json"})
    return config


def test_missing_costs_blocks_without_fabricating_values(tmp_path):
    artifact = compose(fixture(tmp_path, measured=False))
    assert artifact["decision"] == "BLOCK"
    assert artifact["execution_economics_complete"] is False
    assert "COSTS_MISSING" in artifact["blocking_reasons"]
    assert "EXECUTION_COSTS_NOT_FROZEN" in artifact["blocking_reasons"]
    assert artifact["sqcli_authorized"] is False


def test_complete_inputs_produce_a_valid_v4_market_preflight(tmp_path):
    artifact = compose(fixture(tmp_path, measured=True))
    assert artifact["decision"] == "PASS"
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    assert validate_stage_artifact(
        "market_preflight", artifact, receipt, METHODOLOGY,
        "us500-test", "alquimia_native") == []
    assert artifact["next_stage_authorized"] == "hypothesis_screen"
    assert artifact["sqcli_authorized"] is False
    assert artifact["paper_authorized"] is False
    assert artifact["live_authorized"] is False
