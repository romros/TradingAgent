import json
from pathlib import Path


ROOT = Path(__file__).parent


def test_crypto_h4_campaign_is_closed_before_performance_and_matches_universe():
    registration = json.loads((ROOT / "crypto_h4_campaign_preregistration_v4.json").read_text())
    universe = json.loads((ROOT / "campaign_universe_v4.json").read_text())
    registered = registration["markets"]
    campaigns = {row["symbol"]: row for row in universe["campaigns"]}
    assert registration["registration_closed"] is True
    assert registration["performance_accessed"] is False
    assert registration["legacy_candidates_reused"] is False
    assert registration["candidate_ids"] == []
    assert registration["research_authorized"] is False
    assert set(registered) == {"BTCUSD", "ETHUSD"}
    for symbol, row in registered.items():
        assert row["campaign_id"] == campaigns[symbol]["campaign_id"]
        assert registration["directed_hypotheses"]["mechanisms"] == campaigns[symbol]["mechanisms"]
        assert registration["directed_hypotheses"]["directions"] == campaigns[symbol]["directions_per_mechanism"]


def test_crypto_h4_splits_are_ordered_and_holdout_is_common_and_sealed():
    registration = json.loads((ROOT / "crypto_h4_campaign_preregistration_v4.json").read_text())
    holdouts = set()
    for row in registration["markets"].values():
        split = row["temporal_split_utc"]
        periods = [split[name] for name in ("train", "validation", "oos", "final_holdout")]
        assert all(left[0] <= left[1] < right[0] for left, right in zip(periods, periods[1:]))
        assert split["embargo_bars"] == 10
        holdouts.add(tuple(split["final_holdout"]))
    assert len(holdouts) == 1
    assert registration["holdout_accessed"] is False


def test_crypto_h4_profiles_are_bounded_and_stop_protected():
    registration = json.loads((ROOT / "crypto_h4_campaign_preregistration_v4.json").read_text())
    profiles = registration["profile_parameter_ranges"]
    assert set(profiles) == {
        "crypto_h4_channel_breakout_v4", "crypto_h4_time_series_momentum_v4",
        "crypto_h4_volatility_compression_breakout_v4"}
    for values in profiles.values():
        assert 2 <= values["indicator_period_min"] < values["indicator_period_max"] <= 250
        assert 1 <= values["shift_min"] <= values["shift_max"] <= 2
        assert 2 <= values["exit_after_bars_min"] < values["exit_after_bars_max"] <= 30
        assert values["atr_stop_multiple_min"] >= 1
        assert values["atr_stop_multiple_max"] <= 4
    momentum = profiles["crypto_h4_time_series_momentum_v4"]
    assert momentum["roc_threshold_min"] == 0
    assert momentum["roc_threshold_max"] == 15
    assert registration["budgets"]["accepted_candidates_global_budget_shared_with_all_v4_campaigns"] == 60
