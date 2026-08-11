import json
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_experiment_design_v4 import (
    compile_design, iter_unique_points, parameter_axes,
)


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "lab/sq_bridge/crypto_h4_campaign_preregistration_v4.json"


def test_compiles_exact_sealed_design_deterministically():
    first = compile_design(PREREG)
    second = compile_design(PREREG)
    assert first == second
    assert first["directed_hypotheses"] == 18
    assert first["total_screen_points"] == 90_000
    assert first["accepted_candidates_global_budget"] == 60
    assert len({row["hypothesis_id"] for row in first["branches"]}) == 18
    assert {row["market"] for row in first["branches"]} == {"BTCUSD", "ETHUSD"}
    assert {row["direction"] for row in first["branches"]} == {"both", "long", "short"}
    assert all(row["attempts"] == 5_000 for row in first["branches"])
    assert first["market_data_accessed"] is False
    assert first["performance_accessed"] is False
    assert first["research_authorized"] is False


def test_points_file_matches_manifest_hash(tmp_path):
    result = compile_design(PREREG, tmp_path / "points")
    assert len(list((tmp_path / "points").glob("*.jsonl"))) == 18
    for branch in result["branches"]:
        assert branch["points_file_sha256"] == branch["points_sha256"]
        rows = Path(branch["points_path"]).read_text().splitlines()
        assert len(rows) == 5_000
        assert len(set(rows)) == 5_000
        assert json.loads(rows[0])["attempt"] == 1


def test_grid_range_and_cardinality_guards():
    axes = parameter_axes("crypto_h4_channel_breakout_v4", {
        "indicator_period_min": 12, "indicator_period_max": 12,
        "shift_min": 1, "shift_max": 1,
        "exit_after_bars_min": 3, "exit_after_bars_max": 3,
        "exit_after_bars_step": 1, "atr_stop_multiple_min": 1,
        "atr_stop_multiple_max": 1, "atr_stop_multiple_step": .25,
    })
    assert list(iter_unique_points("seed", axes, 1)) == [{
        "indicator_period": 12, "shift": 1, "exit_after_bars": 3,
        "atr_stop_multiple": 1.0}]
    with pytest.raises(ValueError, match="cardinality"):
        list(iter_unique_points("seed", axes, 2))


def test_rejects_preregistration_drift(tmp_path):
    changed = json.loads(PREREG.read_text())
    changed["budgets"]["hypothesis_screen_attempts_per_directed_hypothesis"] = 4_999
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="contract changed"):
        compile_design(path)
