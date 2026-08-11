import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.test_eurusd_d1_hypothesis_trace_v4 import _costs
from lab.sq_bridge.test_us500_d1_hypothesis_trace_v4 import _source
from lab.sq_bridge.us500_d1_market_preflight_v4 import compose
from lab.sq_bridge.us500_v4_screen_bootstrap import bootstrap


ROOT = Path(__file__).parent
CAMPAIGN = "us500-d1-alquimia-v4"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def _preflight(tmp_path: Path, source: Path, costs: Path) -> Path:
    cost_model = json.loads(costs.read_text())
    cost_model.update({"paper_authorized": False, "live_authorized": False})
    _write(costs, cost_model)
    coverage = tmp_path / "coverage.json"
    _write(coverage, {
        "decision": "PASS_HISTORICAL_COVERAGE", "performance_accessed": False,
        "historical_coverage_pass": True, "historical_expected_observations": 1200,
        "historical_complete_observations": 1200,
        "historical_overall_coverage_ratio": 1,
        "historical_minimum_period_coverage_ratio": 1,
        "historical_period_coverage": {"all": 1}})
    mapping = tmp_path / "mapping.json"
    _write(mapping, {
        "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False,
        "common_complete_session_coverage_ratio": 1,
        "d1_close_return_correlation": 1})
    canonical = tmp_path / "canonical.json"
    _write(canonical, {
        "decision": "PASS_CANONICAL_D1_SOURCE", "campaign_id": CAMPAIGN,
        "symbol": "US500", "timeframe": "D1", "performance_accessed": False,
        "holdout_accessed": False, "coverage_sha256": _sha(coverage),
        "mapping_sha256": _sha(mapping), "canonical_path": str(source),
        "canonical_sha256": _sha(source)})
    config = tmp_path / "config.json"
    _write(config, {
        "schema_version": 1, "campaign_id": CAMPAIGN,
        "ostium_pair_id": "US500/USD", "coverage": coverage.name,
        "mapping": mapping.name, "canonical_source": canonical.name,
        "costs": costs.name})
    preflight = tmp_path / "preflight.json"
    _write(preflight, compose(config))
    return preflight


def test_bootstrap_runs_real_us500_screen_without_starting_sqcli(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    result = bootstrap(
        preflight_path=_preflight(tmp_path, source, costs), source_path=source,
        cost_model_path=costs, methodology_path=ROOT / "methodology_v4.json",
        output_dir=tmp_path / "out")
    assert result["decision"] in {"PASS_SQ_BRANCHES_READY", "REJECT_NO_HYPOTHESIS"}
    assert result["sqcli_started"] is False
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
    assert json.loads(Path(result["trace_path"]).read_text())["attempted_variants"] == 27
    assert set(result["branches"]) == set(result["selected_hypothesis_ids"])


def test_bootstrap_binds_exact_source_and_cost_hashes(tmp_path):
    source, costs = _source(tmp_path), _costs(tmp_path)
    preflight = _preflight(tmp_path, source, costs)
    source.write_text(source.read_text() + "\n")
    with pytest.raises(ValueError, match="does not authorize these inputs"):
        bootstrap(
            preflight_path=preflight, source_path=source, cost_model_path=costs,
            methodology_path=ROOT / "methodology_v4.json",
            output_dir=tmp_path / "out")
