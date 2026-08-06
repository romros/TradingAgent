import pandas as pd

from eurusd_london_orb_v25 import metrics, passes, variants


def test_variant_budget_is_frozen_at_72():
    config = {"search": {"range_minutes": [30, 60, 120], "buffer_range_fraction": [0, .1],
              "stop_range_fraction": [.75, 1], "reward_risk": [1, 1.5, 2], "side": ["long", "short"]}}
    assert len(list(variants(config))) == 72


def test_fixed_oracle_cost_can_falsify_small_trade():
    trades = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"], utc=True),
                           "gross_return": [.001], "stop_fraction": [.01]})
    result = metrics(trades, 10, {"capital_usdc": 200, "risk_per_trade_pct": 1,
                                  "opening_oracle_usdc": .1})
    assert result["net_pnl_usdc"] == -.1


def test_gate_requires_sample_and_year_stability():
    gates = {"minimum_base_profit_factor": 1.15, "maximum_drawdown_pct": 20,
             "minimum_positive_year_ratio": .6}
    good = {"trades": 100, "profit_factor": 1.2, "max_drawdown_pct": 10,
            "positive_year_ratio": .8}
    assert passes(good, 100, gates)
    assert not passes({**good, "trades": 99}, 100, gates)
