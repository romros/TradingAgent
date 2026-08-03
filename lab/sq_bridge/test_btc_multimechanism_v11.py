from pathlib import Path

import pandas as pd

from lab.sq_bridge.btc_multimechanism_v11 import aggregate, enrich, grids, load_m1, signals, simulate, stable_regions


def bars(periods=260):
    index = pd.date_range("2020-01-01", periods=periods, freq="h", tz="UTC")
    close = pd.Series([100 + i * .5 for i in range(periods)], index=index)
    return pd.DataFrame({"open": close, "high": close + .2, "low": close - .2, "close": close,
                         "complete": True}, index=index)


def test_aggregate_uses_utc_epoch_and_marks_missing_source_bars():
    index = pd.date_range("2020-01-01", periods=60, freq="min", tz="UTC")
    raw = pd.DataFrame({"open": 1, "high": 2, "low": .5, "close": 1.5, "volume": 1}, index=index)
    assert bool(aggregate(raw, "H1").iloc[0].complete)
    assert not bool(aggregate(raw.drop(index[3]), "H1").iloc[0].complete)


def test_donchian_uses_prior_channel_only():
    frame = enrich(bars())
    entry, _ = signals(frame, "donchian_trend", {"side": "long", "lookback": 20, "exit_lookback": 10, "stop_atr": 2})
    assert entry.iloc[-1]


def test_simulation_enters_next_bar_and_stress_cost_is_higher():
    frame = enrich(bars())
    params = {"side": "long", "lookback": 20, "exit_lookback": 10, "stop_atr": 2}
    costs = {"ostium_opening_fee_bps": 5, "scenarios": {
        "base": {"dynamic_spread_and_impact_bps": 1, "annual_rollover_pct": 8},
        "stress": {"dynamic_spread_and_impact_bps": 10, "annual_rollover_pct": 40}}}
    trades = simulate(frame, "donchian_trend", params, costs)
    assert trades and trades[0]["entry"] > frame.index[20].isoformat()
    assert trades[0]["stress"] < trades[0]["base"]


def test_plural_config_keys_map_to_runtime_side():
    config = {"families": {"x": {"timeframes": ["H1"], "sides": ["long", "short"], "stop_atr": [2]}}}
    assert [params["side"] for _, params in grids(config)] == ["long", "short"]


def test_stable_region_selects_medoid_without_metrics():
    config = {"families": {"x": {"timeframes": ["H1"], "p": [1, 2, 3], "sides": ["long"]}},
              "pre_registered_train_gate": {"minimum_passing_orthogonal_neighbours": 1}}
    rows = []
    for p in (1, 2, 3):
        params = {"p": p, "side": "long", "timeframe": "H1"}
        rows.append({"candidate_id": f"c{p}", "mechanism": "x", "parameters": params,
                     "passes_point_gate": True, "metrics": {"stress": {"profit_factor": 99 - p}}})
    stable, selected = stable_regions(config, rows)
    assert stable == ["c1", "c2", "c3"]
    assert selected[0]["candidate_id"] == "c2"
    assert selected[0]["performance_metrics_used"] is False


def test_signal_is_suppressed_until_lookback_after_gap_is_complete():
    frame = enrich(bars())
    frame.loc[frame.index[-10], "complete"] = False
    entry, _ = signals(frame, "donchian_trend", {"side": "long", "lookback": 20, "exit_lookback": 10, "stop_atr": 2})
    assert not entry.iloc[-1]


def test_loader_interprets_only_requested_period(tmp_path: Path):
    path = tmp_path / "bars.csv"
    path.write_text("2020.01.01,00:00,1,2,.5,1.5,1\n2021.01.01,00:00,2,3,1,2.5,1\n")
    frame = load_m1(path, "2020-01-01", "2020-12-31")
    assert len(frame) == 1 and frame.index[0].year == 2020
