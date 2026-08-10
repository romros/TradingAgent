import json
from pathlib import Path

import pandas as pd
import pytest

from lab.sq_bridge.xauusd_real_yield_dollar_v30b_train import (
    assert_train_only, metrics, simulate_episode,
)

CONFIG = json.loads(Path(__file__).with_name("family_xauusd_real_yield_dollar_v30b.json").read_text())


def frame(prices):
    index = pd.date_range("2014-01-08", periods=len(prices), freq="15min", tz="UTC")
    return pd.DataFrame({"open": prices, "high": prices, "low": prices,
                         "close": prices, "minute_count": 15}, index=index)


def episode(side=1):
    return {"decision_time_utc": "2014-01-08T00:00:00Z", "side": side, "weeks": 1}


def test_requires_passed_macro_gate_and_sealed_future():
    assert_train_only(CONFIG, {"decision": "PASS_TO_TRAIN_PERFORMANCE"})
    with pytest.raises(ValueError, match="did not authorize"):
        assert_train_only(CONFIG, {"decision": "REJECT_MACRO_FREQUENCY"})


def test_time_exit_applies_costs_and_no_credit():
    prices = [100 + index * .01 for index in range(4)] + [100.04]
    trade = simulate_episode(frame(prices), episode(), pd.Timestamp("2014-01-08T01:00:00Z"),
                             CONFIG, "base")
    assert trade is not None
    assert trade["exit_reason"] == "state"
    assert trade["carry_cost_usdc"] == 0
    assert trade["variable_and_oracle_cost_usdc"] > .1


def test_no_tick_minutes_do_not_discard_a_valid_bar():
    data = frame([100, 100.1, 100.2, 100.3, 100.4])
    data.loc[data.index[0], "minute_count"] = 1
    trade = simulate_episode(data, episode(), pd.Timestamp("2014-01-08T01:00:00Z"),
                             CONFIG, "base")
    assert trade is not None


def test_fixed_stop_precedes_liquidation_in_base_case():
    prices = [100, 99, 94, 94, 94]
    data = frame(prices)
    data.loc[data.index[2], "low"] = 94
    trade = simulate_episode(data, episode(), pd.Timestamp("2014-01-08T01:00:00Z"),
                             CONFIG, "base")
    assert trade is not None
    assert trade["exit_reason"] in {"gap_stop", "stop"}
    assert not trade["liquidated"]


def test_metrics_include_initial_capital_in_drawdown():
    rows = [{"net_pnl_usdc": -3, "entry_time": "2014-01-08T00:00:00Z",
             "liquidated": False, "exit_reason": "stop", "elapsed_days": 1,
             "gross_pnl_usdc": -2, "variable_and_oracle_cost_usdc": .5,
             "carry_cost_usdc": .5, "side": 1},
            {"net_pnl_usdc": 1, "entry_time": "2014-02-08T00:00:00Z",
             "liquidated": False, "exit_reason": "state", "elapsed_days": 1,
             "gross_pnl_usdc": 2, "variable_and_oracle_cost_usdc": .5,
             "carry_cost_usdc": .5, "side": -1}]
    result = metrics(rows, 200)
    assert result["max_drawdown_pct"] == pytest.approx(1.5)
    assert result["stop_count"] == 1
    assert result["gross_pnl_usdc"] == 0
    assert result["long_trades"] == result["short_trades"] == 1
