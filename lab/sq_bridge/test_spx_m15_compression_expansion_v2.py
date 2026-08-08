from spx_m15_compression_expansion_v2 import leverage_plan


def test_leverage_respects_margin_and_liquidation_buffer():
    account = {"risk_per_trade_pct": 1, "maximum_margin_pct": 35,
               "venue_max_leverage": 200, "liquidation_buffer_over_stop": 1.5}
    plan = leverage_plan(0.005, account)
    assert plan is not None
    assert plan["margin"] <= 0.35
    assert plan["leverage"] <= 200


def test_impossibly_wide_stop_is_rejected():
    account = {"risk_per_trade_pct": 1, "maximum_margin_pct": 0.1,
               "venue_max_leverage": 200, "liquidation_buffer_over_stop": 1.5}
    assert leverage_plan(2.0, account) is None
