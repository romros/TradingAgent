import json
from pathlib import Path

from lab.sq_bridge.crypto_h4_region_selector_v4 import (
    normalized_distance, regions_for_branch, select_global,
)


ROOT = Path(__file__).resolve().parents[2]
PREREG = json.loads((ROOT / "lab/sq_bridge/crypto_h4_campaign_preregistration_v4.json").read_text())


def _branch(hypothesis="btcusd_channel_breakout_long_v4"):
    return {"hypothesis_id": hypothesis, "campaign_id": "btcusd-h4-alquimia-v4",
            "market": "BTCUSD", "mechanism": "channel_breakout",
            "direction": "long", "profile": "crypto_h4_channel_breakout_v4"}


def _row(attempt, period, passed=True, ev=1.0):
    scenario = {"net_pnl_usdc": 10, "expectancy_usdc_per_trade": ev,
                "profit_factor": 1.5, "max_drawdown_usdc": 4,
                "positive_calendar_years_ratio": .8}
    return {"attempt": attempt,
            "parameters": {"indicator_period": period, "shift": 1,
                           "exit_after_bars": 10, "atr_stop_multiple": 2.0},
            "decision": "PASS_POINT" if passed else "REJECT_POINT",
            "closed_trades": 70,
            "scenarios": {name: dict(scenario) for name in
                          ("base", "conservative", "stress")}}


def test_stable_region_requires_two_of_four_nearest_passing():
    rows = [_row(1, 50, ev=2), _row(2, 51), _row(3, 49),
            _row(4, 52, False), _row(5, 48, False), _row(6, 120, True)]
    regions = regions_for_branch(rows, _branch(), PREREG)
    central = next(row for row in regions if row["central_attempt"] == 1)
    assert central["member_attempts"] == [1, 2, 3]
    assert central["nearest_points_considered"] == [2, 3, 4, 5]
    assert 6 not in central["member_attempts"]


def test_overlapping_regions_keep_best_ranked_once():
    rows = [_row(1, 50, ev=2), _row(2, 51, ev=1), _row(3, 49, ev=.5),
            _row(4, 52, False), _row(5, 48, False)]
    result = select_global(regions_for_branch(rows, _branch(), PREREG))
    assert len(result["selected_regions"]) == 1
    assert result["selected_regions"][0]["central_attempt"] == 1
    assert result["suppressed_regions"]


def test_different_hypotheses_do_not_suppress_each_other():
    rows = [_row(1, 50), _row(2, 51), _row(3, 49),
            _row(4, 52, False), _row(5, 48, False)]
    regions = (regions_for_branch(rows, _branch("h1"), PREREG)
               + regions_for_branch(rows, _branch("h2"), PREREG))
    result = select_global(regions)
    assert len(result["selected_regions"]) == 2
    assert {row["hypothesis_id"] for row in result["selected_regions"]} == {"h1", "h2"}


def test_global_budget_is_applied_after_overlap_suppression():
    rows = [_row(1, 50), _row(2, 51), _row(3, 49),
            _row(4, 52, False), _row(5, 48, False)]
    template = regions_for_branch(rows, _branch(), PREREG)[0]
    regions = []
    for index in range(61):
        region = dict(template)
        region["hypothesis_id"] = f"independent_{index}"
        region["candidate_id"] = f"candidate_{index}"
        regions.append(region)
    result = select_global(regions)
    assert len(result["selected_regions"]) == 60
    assert result["suppressed_regions"][-1]["reason"] == \
        "GLOBAL_ACCEPTED_CANDIDATE_BUDGET_60"
