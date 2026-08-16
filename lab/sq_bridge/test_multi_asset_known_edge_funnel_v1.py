from lab.sq_bridge.multi_asset_known_edge_funnel_v1 import in_period, pool


def test_period_requires_entry_and_exit_inside_window():
    assert in_period({"entry": "2024-01-02", "exit": "2024-01-10"},
                     "2024-01-01", "2024-12-31")
    assert not in_period({"entry": "2023-12-29", "exit": "2024-01-10"},
                         "2024-01-01", "2024-12-31")


def test_pool_is_equal_weight_and_not_worst_asset_drawdown():
    rows = [
        {"metrics": {"trades": 1, "return_pct": 10}, "wins": 100, "loss": 0,
         "selected": [{"exit": "2024-01-02", "pnl": 100}]},
        {"metrics": {"trades": 1, "return_pct": -5}, "wins": 0, "loss": 50,
         "selected": [{"exit": "2024-01-03", "pnl": -50}]},
    ]
    result = pool(rows, 1000)
    assert result["trades"] == 2
    assert result["profit_factor"] == 2
    assert result["return_pct"] == 2.5
    assert round(result["maximum_drawdown_pct"], 6) == round(25 / 1050 * 100, 6)
