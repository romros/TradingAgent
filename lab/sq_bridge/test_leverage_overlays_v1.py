from lab.sq_bridge import four_edge_leverage_overlay_screen_v1 as overlay


def test_constant_leverage_uses_calendar_time_and_remains_rejected():
    result = overlay.screen()
    assert result["decision"] == "REJECT_LEVERAGE_OVERLAY"
    assert 10.4 < result["analytical_overlay"]["net_return_pct"] < 10.5
    assert result["analytical_overlay"]["maximum_drawdown_pct"] < result["spy_buy_hold"]["maximum_drawdown_pct"]
    assert result["exact_native_rebuild_required"] is False
