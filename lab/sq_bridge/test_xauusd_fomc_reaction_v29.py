import json
from pathlib import Path

import pandas as pd
import pytest

from lab.sq_bridge.xauusd_fomc_reaction_v29 import (
    parameter_grid, preflight, selected_venue_leverage, simulate_window,
)

CONFIG = json.loads(Path(__file__).with_name("family_xauusd_fomc_reaction_v29.json").read_text())


def window(entry=101.0, exit_=102.0, lows=(100.8, 100.7), highs=(101.2, 102.2)):
    index = pd.date_range("2020-01-01T14:15:00Z", periods=2, freq="15min")
    path = pd.DataFrame({"open": [entry, 101.5], "high": highs, "low": lows,
                         "close": [101.5, exit_]}, index=index)
    return {"event_date": "2020-01-01", "reaction_open": 100.0, "entry": entry,
            "exit": exit_, "path": path}


def test_contract_has_exactly_sixteen_points_and_sealed_future():
    assert len(parameter_grid(CONFIG)) == CONFIG["search"]["attempt_budget"] == 16
    assert CONFIG["splits"]["train"] == ["2015-01-01", "2018-12-31"]
    assert CONFIG["splits"]["sealed_holdout"][0] == "2024-01-01"
    assert CONFIG["validation_accessed"] is False
    assert CONFIG["holdout_evaluated"] is False


def test_continuation_and_reversal_use_only_observed_reaction_direction():
    continuation = simulate_window(window(), "continuation", .005, 50)
    reversal = simulate_window(window(), "reversal", .005, 50)
    assert continuation["direction"] == 1 and continuation["gross_return"] > 0
    assert reversal["direction"] == -1 and reversal["gross_return"] < 0


def test_stop_and_gap_liquidation_order_are_conservative():
    stopped = simulate_window(window(lows=(100.4, 100.3)), "continuation", .005, 50)
    assert stopped["exit_reason"] == "stop"
    assert stopped["gross_return"] == pytest.approx(-.005)
    gapped = window(lows=(98, 98), highs=(101, 101))
    gapped["path"].iloc[0, gapped["path"].columns.get_loc("open")] = 98
    liquidated = simulate_window(gapped, "continuation", .005, 50)
    assert liquidated["exit_reason"] == "liquidation_gap"
    assert liquidated["liquidated"] is True


def test_maximum_safe_venue_leverage_is_used_with_stop_buffer():
    assert selected_venue_leverage(.005, CONFIG["economics"]) == 50
    assert selected_venue_leverage(.0075, CONFIG["economics"]) == 50
    changed = json.loads(json.dumps(CONFIG))
    changed["economics"]["venue_max_leverage"] = 200
    assert selected_venue_leverage(.005, changed["economics"]) == 160


def test_runtime_refuses_attempt_budget_drift():
    changed = json.loads(json.dumps(CONFIG))
    changed["search"]["attempt_budget"] = 15
    with pytest.raises(ValueError, match="attempt contract mismatch"):
        parameter_grid(changed)


def test_preflight_uses_frozen_minimum_trade_coverage_not_imputation(tmp_path):
    changed = json.loads(json.dumps(CONFIG))
    changed["splits"]["train"] = ["2020-01-01", "2020-01-03"]
    changed["train_gate"]["minimum_complete_event_windows"] = 1
    calendar = {"events": [{"date": "2020-01-01"}, {"date": "2020-01-02"}]}
    index = pd.date_range("2020-01-01T19:00:00Z", periods=11, freq="15min")
    frame = pd.DataFrame({"open": 100, "high": 101, "low": 99, "close": 100,
                          "minute_count": 15}, index=index)
    fixture = tmp_path / "technical-fixture"
    fixture.write_text("fixture")
    result = preflight(frame, calendar, changed, [fixture])
    assert result["decision"] == "PASS"
    assert result["complete_train_event_windows"] == 1
    assert result["incomplete_event_dates"] == ["2020-01-02"]
