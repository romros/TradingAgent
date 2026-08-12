from lab.sq_bridge.ibkr_spy_d1_discovery_v1 import compile_batch


def test_direct_spy_batch_is_cost_aware_and_long_only(tmp_path):
    result = compile_batch(tmp_path, 1)
    assert result["decision"] == "PASS_CFX_BATCH_READY"
    assert result["campaign_type"] == "SPY_DIRECT_COST_AWARE"
    assert result["commission_round_trip_usd"] == 2
    assert set(result["projects"]) == {
        "spy_d1_direct_generic_long_v1",
        "spy_d1_direct_volatility_trend_long_v1",
    }
    for project in result["projects"].values():
        assert project["sq_genetic_shape"]["nominal_evaluations"] == 10000
