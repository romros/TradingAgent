from datetime import datetime, timedelta, timezone

import numpy as np

from lab.sq_bridge.crypto_h4_train_engine_v4 import (
    Bars, evaluate_point, load_train, metrics, signals, simulate,
)


def _bars(rows, gap_at=None):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stamps = []
    for index in range(len(rows)):
        offset = index + (1 if gap_at is not None and index >= gap_at else 0)
        stamps.append(start + timedelta(hours=4 * offset))
    arrays = [np.asarray([row[column] for row in rows], dtype=float)
              for column in range(4)]
    segment = np.zeros(len(rows), dtype=np.int64)
    if gap_at is not None: segment[gap_at:] = 1
    return Bars(tuple(stamps), *arrays, segment)


def _channel_params(**overrides):
    result = {"indicator_period": 2, "shift": 1, "exit_after_bars": 1,
              "atr_stop_multiple": 10.0}
    result.update(overrides)
    return result


def test_next_open_entry_and_stop_has_same_bar_priority():
    # o,h,l,c: bar 14 closes above both preceding highs, entry is bar 15 open.
    rows = [(100, 101, 99, 100)] * 13 + [
        (100, 101, 99, 100), (100, 105, 99, 104), (103, 110, 90, 108)]
    bars = _bars(rows)
    trades = simulate(bars, "channel_breakout", "long",
                      _channel_params(atr_stop_multiple=1.0))
    assert len(trades) == 1
    trade = trades[0]
    assert trade.entry_index == 15 and trade.entry_price == 103
    assert trade.exit_reason == "stop"  # It was also the one-bar time exit.
    assert trade.exit_price < trade.entry_price


def test_trade_crossing_missing_h4_bar_is_excluded():
    rows = [(100, 101, 99, 100)] * 13 + [
        (100, 101, 99, 100), (100, 105, 99, 104),
        (104, 106, 103, 105), (105, 107, 104, 106)]
    trades = simulate(_bars(rows, gap_at=16), "channel_breakout", "long",
                      _channel_params(exit_after_bars=2))
    assert trades == []


def test_loader_never_parses_prices_after_train_end(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text(
        "2020.01.01,00:00,100,101,99,100,1\n"
        "2020.01.01,04:00,101,102,100,101,1\n"
        "2020.01.01,08:00,SECRET,SECRET,SECRET,SECRET,SECRET\n")
    bars = load_train(path, datetime(2020, 1, 1, tzinfo=timezone.utc),
                      datetime(2020, 1, 1, 4, tzinfo=timezone.utc))
    assert len(bars) == 2


def test_ostium_costs_are_applied_at_exactly_200_usdc():
    bars = _bars([(100, 101, 99, 100)] * 13 + [
        (100, 101, 99, 100), (100, 105, 99, 104), (104, 106, 103, 105)])
    trades = simulate(bars, "channel_breakout", "long", _channel_params())
    costs = {"by_notional": {"200": {
        "base_roundtrip_bps": 10, "conservative_roundtrip_bps": 20,
        "stress_roundtrip_bps": 40}}, "carry": {
        "long": {"base_annual_cost_pct": 0, "conservative_annual_cost_pct": 0,
                 "stress_annual_cost_pct": 0},
        "short": {"base_annual_cost_pct": 0, "conservative_annual_cost_pct": 0,
                  "stress_annual_cost_pct": 0}}}
    base, stress = metrics(trades, costs, "base"), metrics(trades, costs, "stress")
    assert base["notional_usdc"] == 200
    assert base["net_pnl_usdc"] > stress["net_pnl_usdc"]


def test_momentum_negative_threshold_ambiguity_is_skipped():
    rows = [(100 + index, 101 + index, 99 + index, 100 + index)
            for index in range(20)]
    long, short, _ = signals(_bars(rows), "time_series_momentum", "both", {
        "indicator_period": 2, "shift": 1, "roc_threshold_pct": -50})
    assert not long.any() and not short.any()


def test_point_rejection_exposes_only_train_metrics():
    bars = _bars([(100, 101, 99, 100)] * 20)
    costs = {"by_notional": {"200": {
        "base_roundtrip_bps": 10, "conservative_roundtrip_bps": 20,
        "stress_roundtrip_bps": 40}}, "carry": {
        side: {f"{scenario}_annual_cost_pct": 0 for scenario in
               ("base", "conservative", "stress")} for side in ("long", "short")}}
    result = evaluate_point(bars, "channel_breakout", "both", _channel_params(), costs)
    assert result["decision"] == "REJECT_POINT"
    assert result["scenarios"]["stress"]["calendar_years"] == 1
    assert result["validation_accessed"] is False
    assert result["holdout_accessed"] is False
