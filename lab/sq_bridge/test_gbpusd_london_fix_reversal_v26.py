import json
from pathlib import Path

import pandas as pd

from lab.sq_bridge.gbpusd_london_fix_reversal_v26 import daily_signals, metrics, neighbors, run


CONFIG = json.loads(Path(__file__).with_name("family_gbpusd_london_fix_reversal_v26.json").read_text())


def test_campaign_is_frozen_train_only_and_has_twelve_points():
    assert CONFIG["splits"]["train"] == ["2007-01-01", "2013-12-31"]
    assert CONFIG["splits"]["sealed_holdout"][0] == "2024-01-01"
    assert CONFIG["search"]["attempt_budget"] == 12
    assert CONFIG["economics"]["capital_usdc"] == 200
    assert CONFIG["holdout_evaluated"] is False


def test_daily_signal_uses_prior_twenty_days_without_lookahead():
    index = pd.DatetimeIndex(
        [timestamp for day in pd.bdate_range("2026-01-01", periods=21)
         for timestamp in (day.tz_localize("Europe/London") + pd.Timedelta(hours=15),
                           day.tz_localize("Europe/London") + pd.Timedelta(hours=16))]
    )
    opens = [1.0 if timestamp.hour == 15 else 1.001 for timestamp in index]
    frame = pd.DataFrame({"o": opens, "h": 1.01, "l": .99, "c": opens}, index=index)
    signals = daily_signals(frame)
    assert len(signals) == 21
    assert pd.isna(signals.iloc[19].baseline)
    assert signals.iloc[20].baseline > 0


def test_metrics_include_fixed_oracle_and_never_claim_live():
    trades = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"], utc=True),
                           "gross_return": [0.01], "stop_fraction": [0.01], "adverse_fraction": [0.005]})
    result = metrics(trades, 0, CONFIG["economics"])
    assert result["expectancy_usdc"] == 1.9
    assert result["maximum_effective_leverage"] == 1.0


def test_stability_requires_an_adjacent_parameter_point():
    axes = [[1.0, 1.5], [.5, 1.0], [17, 18]]
    passing = {(1.0, .5, 17), (1.5, .5, 17)}
    assert neighbors((1.0, .5, 17), passing, axes) == 1


def test_no_friction_diagnostic_cannot_change_the_frozen_gate(tmp_path, monkeypatch):
    frame = pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC"))
    monkeypatch.setattr("lab.sq_bridge.gbpusd_london_fix_reversal_v26.load_m15", lambda _: frame)
    source = tmp_path / "unused.parquet"; source.write_bytes(b"fixture")
    result = run(source, CONFIG)
    assert result["decision"] == "REJECT_NO_SQ"
    assert all("gross_no_cost_no_oracle_diagnostic" in row for row in result["all_results"])
