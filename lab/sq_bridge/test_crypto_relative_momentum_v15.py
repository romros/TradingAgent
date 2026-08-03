import pandas as pd

from lab.sq_bridge.crypto_relative_momentum_v15 import parameter_grid, simulate


def market(slope):
    index = pd.date_range("2023-01-01", periods=150, freq="D", tz="UTC")
    close = pd.Series([100 + slope * at for at in range(150)], index=index)
    return pd.DataFrame({"open": close, "high": close + .1, "low": close - .1, "close": close,
                         "complete": True, "atr_14": 2.0, "atr_28": 2.0}, index=index)


def costs():
    return {"opening_fee_bps_per_leg": 0, "oracle_fee_usdc_per_leg": .1, "scenarios": {
        "base": {"dynamic_spread_and_impact_bps_per_leg": 0, "annual_rollover_pct_per_leg": 0},
        "stress": {"dynamic_spread_and_impact_bps_per_leg": 10, "annual_rollover_pct_per_leg": 40}}}


def test_relative_rank_uses_prior_closes_and_selects_strongest_weakest():
    frames = {"BTCUSD": market(.5), "ETHUSD": market(0), "SOLUSD": market(-.2)}
    params = {"mode": "long_strongest_short_weakest", "lookback_days": 7, "hold_days": 1,
              "volatility_lookback_days": 14, "stop_atr": 2.0}
    small = {"total_risk_per_portfolio_trade_pct": 1, "capital_usdc": 200}
    trades = simulate(frames, params, costs(), small)
    assert trades and trades[0]["assets"] == ["BTCUSD", "SOLUSD"]
    assert trades[0]["sides"] == ["long", "short"]
    assert trades[0]["stress"] < trades[0]["base"]
    assert trades[0]["oracle_cost_usdc"] == .2
    assert trades[0]["effective_notional_to_capital"] > 0


def test_registered_grid_has_192_points():
    config = {"grid": {"mode": ["long_strongest", "long_strongest_short_weakest"],
                       "lookback_days": [7, 14, 28, 56, 84, 112], "hold_days": [1, 3, 7, 14],
                       "volatility_lookback_days": [14, 28], "stop_atr": [2.0, 3.0], "points": 192}}
    assert len(list(parameter_grid(config))) == 192


def test_dual_momentum_stays_in_cash_when_all_assets_are_negative():
    frames = {"BTCUSD": market(-.05), "ETHUSD": market(-.1), "SOLUSD": market(-.2)}
    params = {"mode": "long_strongest_if_positive", "lookback_days": 7, "hold_days": 1,
              "volatility_lookback_days": 14, "stop_atr": 2.0}
    assert simulate(frames, params, costs(), {"total_risk_per_portfolio_trade_pct": 1, "capital_usdc": 200}) == []
