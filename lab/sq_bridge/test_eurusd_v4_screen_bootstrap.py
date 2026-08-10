import json

import pytest

from lab.sq_bridge.eurusd_v4_screen_bootstrap import bootstrap
from lab.sq_bridge.eurusd_d1_market_preflight_v4 import compose
from lab.sq_bridge.test_eurusd_d1_hypothesis_trace_v4 import _costs, _source, ROOT


def _preflight(tmp_path, costs):
    def write(name, value):
        (tmp_path / name).write_text(json.dumps(value))
    cost_model = json.loads(costs.read_text())
    cost_model.update({"instrument": {"pair_id": "2", "pair_from": "EUR",
                       "pair_to": "USD"}, "paper_authorized": False,
                       "live_authorized": False})
    costs.write_text(json.dumps(cost_model, sort_keys=True) + "\n")
    write("coverage.json", {"symbol": "EURUSD", "timeframe": "D1",
          "decision": "PASS_HISTORICAL_COVERAGE", "performance_accessed": False,
          "historical_coverage_pass": True, "historical_expected_observations": 100,
          "historical_complete_observations": 99,
          "historical_overall_coverage_ratio": .99,
          "historical_minimum_period_coverage_ratio": .9,
          "historical_period_coverage": {"2020": .9}})
    write("mapping.json", {"symbol": "EURUSD", "timeframe": "D1",
          "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False,
          "dukascopy_ostium_mapping": {"common_day_coverage_ratio": 1,
                                       "d1_close_return_correlation": .9999}})
    write("resource.json", {"decision": "PASS_SQ_D1_RESOURCE",
          "performance_accessed": False, "ohlc_match_ratio": 1,
          "sunday_fragment_bars": 0})
    config = tmp_path / "config.json"
    write("config.json", {"schema_version": 1,
          "preflight_composer": "eurusd_d1_v4",
          "campaign_id": "eurusd-v4-test", "ostium_pair_id": "EUR/USD",
          "coverage": "coverage.json", "mapping": "mapping.json",
          "sq_resource": "resource.json", "costs": costs.name})
    path = tmp_path / "preflight.json"
    path.write_text(json.dumps(compose(config), indent=2, sort_keys=True) + "\n")
    return path


def test_bootstrap_rejects_cleanly_without_spending_sqcli(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    result = bootstrap(
        preflight_path=_preflight(tmp_path, costs), source_path=source,
        cost_model_path=costs, methodology_path=ROOT / "methodology_v4.json",
        output_dir=tmp_path / "out")
    assert result["decision"] == "REJECT_NO_HYPOTHESIS"
    assert result["selected_hypothesis_ids"] == []
    assert result["branches"] == {}
    assert result["sqcli_started"] is False
    assert result["paper_authorized"] is False
    assert (tmp_path / "out/bootstrap.json").is_file()


def test_bootstrap_binds_preflight_to_exact_frozen_cost_model(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, costs)
    costs.write_text(costs.read_text() + "\n")
    with pytest.raises(ValueError, match="does not authorize this cost model"):
        bootstrap(
            preflight_path=preflight, source_path=source,
            cost_model_path=costs, methodology_path=ROOT / "methodology_v4.json",
            output_dir=tmp_path / "out")
