import pandas as pd

from lab.sq_bridge.gbpusd_m15_donchian_v2 import metrics


def test_metrics_caps_leverage_at_twenty():
    trades = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01"], utc=True),
        "gross": [.001], "stop": [.00001], "bars": [4],
    })
    result = metrics(trades, 0)
    assert result["max_leverage"] == 20
    assert result["net_usdc"] == 4


def test_round_trip_cost_is_charged_on_notional():
    trades = pd.DataFrame({
        "date": pd.to_datetime(["2020-01-01"], utc=True),
        "gross": [.001], "stop": [.01], "bars": [4],
    })
    assert metrics(trades, 10)["net_usdc"] == 0
