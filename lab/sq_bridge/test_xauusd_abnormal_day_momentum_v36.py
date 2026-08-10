import json
from pathlib import Path

from lab.sq_bridge.evidence_chain import verify


ROOT = Path(__file__).parent
FAMILY = json.loads((ROOT / "family_xauusd_abnormal_day_momentum_v36.json").read_text())


def test_v36_grid_and_future_periods_are_frozen_before_performance():
    search = FAMILY["search"]
    attempts = (len(search["lookback_sessions"])
                * len(search["standard_deviations"])
                * len(search["entry_time"])
                * len(search["stop_fraction"]))
    assert attempts == search["attempt_budget"] == 36
    assert FAMILY["splits"]["train"] == ["2007-01-01", "2014-12-31"]
    assert FAMILY["splits"]["sealed_holdout"] == ["2023-01-01", "2026-12-31"]
    assert FAMILY["performance_accessed"] is False
    assert FAMILY["validation_accessed"] is False
    assert FAMILY["oos_accessed"] is False
    assert FAMILY["holdout_evaluated"] is False
    assert FAMILY["independence"].startswith("New campaign")


def test_v36_chain_is_native_and_ready_only_for_discovery():
    result = verify(
        json.loads((ROOT / "evidence/xauusd_abnormal_day_momentum_v36_chain.json").read_text()),
        ROOT / "methodology_v3.json",
    )
    assert result["valid"] is True
    assert result["next_stage"] == "discovery"
    assert result["paper_ready"] is False
    assert result["live_authorized"] is False
