import pandas as pd

from lab.sq_bridge.xauusd_cftc_managed_money_v34_train import first_bar, metrics


def test_first_bar_enforces_delay():
    frame = pd.DataFrame(index=pd.to_datetime(["2020-01-01T01:00:00Z"]))
    assert first_bar(frame, pd.Timestamp("2020-01-01T00:00:00Z"), 2) == frame.index[0]
    assert first_bar(frame, pd.Timestamp("2019-12-31T00:00:00Z"), 2) is None


def test_metrics_separates_directions():
    rows = [{"net_pnl_usdc": 2, "gross_pnl_usdc": 3, "entry_time": "2020-01-01T00:00:00Z",
             "side": 1, "liquidated": False, "holding_days": 7},
            {"net_pnl_usdc": -1, "gross_pnl_usdc": -0.5, "entry_time": "2020-02-01T00:00:00Z",
             "side": -1, "liquidated": False, "holding_days": 7}]
    result = metrics(rows, 200)
    assert result["profit_factor"] == 2
    assert result["long_net_pnl_usdc"] == 2
    assert result["short_net_pnl_usdc"] == -1
