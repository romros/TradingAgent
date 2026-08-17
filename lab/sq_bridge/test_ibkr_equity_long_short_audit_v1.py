from datetime import datetime, timedelta

from lab.sq_bridge.ibkr_equity_long_short_audit_v1 import simulate


def test_short_profit_and_borrow_are_directionally_correct():
    opened = datetime(2023, 1, 2)
    order = {"side": "short", "open_time": opened,
             "close_time": opened + timedelta(days=10),
             "open_price": 50.0, "close_price": 45.0}
    result = simulate([order], 1000, "stress")
    assert result["short_trades"] == 1
    assert result["return_pct"] > 0
    assert result["short_borrow_cost_usd"] > 0


def test_adverse_slippage_reduces_long_and_short_results():
    opened = datetime(2023, 1, 2)
    rows = [
        {"side": "long", "open_time": opened,
         "close_time": opened + timedelta(days=2), "open_price": 40., "close_price": 41.},
        {"side": "short", "open_time": opened + timedelta(days=3),
         "close_time": opened + timedelta(days=5), "open_price": 40., "close_price": 39.},
    ]
    assert simulate(rows, 1000, "stress")["return_pct"] \
        < simulate(rows, 1000, "fixed")["return_pct"]
