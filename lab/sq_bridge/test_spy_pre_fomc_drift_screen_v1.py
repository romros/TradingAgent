from datetime import date

from lab.sq_bridge.spy_pre_fomc_drift_screen_v1 import event_trades, metrics


def test_event_uses_immediately_previous_close_and_whole_shares():
    market = [(date(2024, 1, 1), 100.0), (date(2024, 1, 2), 102.0), (date(2024, 1, 3), 90.0)]
    rows = event_trades(market, {date(2024, 1, 2)}, 250.0, 1.0, 10.0)
    assert len(rows) == 1
    assert rows[0]["entry"] == date(2024, 1, 1)
    assert rows[0]["shares"] == 2
    assert rows[0]["net_pnl"] < 4.0
    assert metrics(rows, 250.0)["events"] == 1
