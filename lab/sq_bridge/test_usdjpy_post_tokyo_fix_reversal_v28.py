import json
from pathlib import Path

import pandas as pd
import pytest

from lab.sq_bridge.usdjpy_post_tokyo_fix_reversal_v28 import run, simulate_short


CONFIG = json.loads(Path(__file__).with_name("family_usdjpy_post_tokyo_fix_reversal_v28.json").read_text())


def test_campaign_uses_fresh_development_and_exact_six_points():
    assert CONFIG["splits"]["train"] == ["2015-01-01", "2018-12-31"]
    assert CONFIG["splits"]["sealed_holdout"][0] == "2024-01-01"
    assert CONFIG["search"]["attempt_budget"] == 6
    assert len(CONFIG["search"]["exit_jst_hour"]) * len(CONFIG["search"]["stop_fraction"]) == 6
    assert CONFIG["validation_accessed"] is False and CONFIG["holdout_evaluated"] is False


def test_short_return_and_stop_are_directionally_correct():
    windows = pd.DataFrame({"date": [pd.Timestamp("2020-01-01").date()],
                            "entry_time": pd.to_datetime(["2020-01-01"], utc=True),
                            "entry": [100.0], "exit": [99.0], "low": [98.0], "high": [100.1]})
    win = simulate_short(windows, .002)
    assert win.iloc[0].gross_return == .01
    windows.loc[0, "high"] = 100.3
    stopped = simulate_short(windows, .002)
    assert round(stopped.iloc[0].gross_return, 6) == -.002


def test_cost_model_preserves_refundable_oracle_semantics():
    assert CONFIG["economics"]["oracle_net_cost_usdc"]["base"] == 0
    assert CONFIG["economics"]["oracle_net_cost_usdc"]["stress"] == .1
    assert CONFIG["economics"]["roundtrip_bps"] == {"base": 5, "conservative": 8, "stress": 15}


def test_runtime_rejects_attempt_budget_drift_before_loading_data(tmp_path):
    changed = json.loads(json.dumps(CONFIG))
    changed["search"]["attempt_budget"] = 7
    with pytest.raises(ValueError, match="attempt contract mismatch"):
        run(tmp_path / "must-not-be-read.parquet", changed)
