import json
from pathlib import Path

from lab.sq_bridge.eurusd_d1_market_preflight_v4 import compose
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent
METHODOLOGY = json.loads((ROOT / "methodology_v4.json").read_text())


def write(path, value):
    path.write_text(json.dumps(value))


def fixture(tmp_path, *, mature):
    write(tmp_path / "coverage.json", {"symbol": "EURUSD", "timeframe": "D1",
          "decision": "PASS_HISTORICAL_COVERAGE", "performance_accessed": False,
          "historical_coverage_pass": True, "historical_expected_observations": 100,
          "historical_complete_observations": 99, "historical_overall_coverage_ratio": .99,
          "historical_minimum_period_coverage_ratio": .9,
          "historical_period_coverage": {"2020": .9}})
    write(tmp_path / "mapping.json", {"symbol": "EURUSD", "timeframe": "D1",
          "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False,
          "dukascopy_ostium_mapping": {"common_day_coverage_ratio": 1,
                                       "d1_close_return_correlation": .9999}})
    write(tmp_path / "resource.json", {"decision": "PASS_SQ_D1_RESOURCE",
          "performance_accessed": False, "ohlc_match_ratio": 1,
          "sunday_fragment_bars": 0})
    if mature:
        write(tmp_path / "costs.json", {"decision": "PASS_COSTS_FROZEN",
              "costs_frozen": True, "instrument": {"pair_id": "2", "pair_from": "EUR",
              "pair_to": "USD"}, "by_notional": {"200": {"base_roundtrip_bps": 4}},
              "paper_authorized": False, "live_authorized": False})
    config = tmp_path / "config.json"
    write(config, {"schema_version": 1, "preflight_composer": "eurusd_d1_v4",
          "campaign_id": "eur-test",
          "ostium_pair_id": "EUR/USD", "coverage": "coverage.json",
          "mapping": "mapping.json", "sq_resource": "resource.json",
          "costs": "costs.json"})
    return config


def test_missing_costs_blocks_before_sq(tmp_path):
    result = compose(fixture(tmp_path, mature=False))
    assert result["decision"] == "BLOCK"
    assert "EXECUTION_COSTS_NOT_FROZEN" in result["blocking_reasons"]
    assert result["sqcli_authorized"] is False


def test_mature_inputs_only_authorize_hypothesis_screen(tmp_path):
    result = compose(fixture(tmp_path, mature=True))
    assert result["decision"] == "PASS"
    assert result["next_stage_authorized"] == "hypothesis_screen"
    assert result["sqcli_authorized"] is False
    receipt = {"decision": "PASS", "candidate_ids": [], "holdout_accessed": False}
    assert validate_stage_artifact("market_preflight", result, receipt, METHODOLOGY,
                                   "eur-test", "alquimia_native") == []


def test_failed_sq_resource_blocks_even_with_mature_costs(tmp_path):
    config = fixture(tmp_path, mature=True)
    write(tmp_path / "resource.json", {"decision": "BLOCK_SQ_D1_RESOURCE_SESSION",
          "performance_accessed": False, "ohlc_match_ratio": .23,
          "sunday_fragment_bars": 1188})
    result = compose(config)
    assert result["decision"] == "BLOCK"
    assert "SQ_D1_RESOURCE_NOT_PASS" in result["blocking_reasons"]
