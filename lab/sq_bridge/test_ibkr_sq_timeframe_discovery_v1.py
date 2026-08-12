from lab.sq_bridge.ibkr_sq_timeframe_discovery_v1 import compile_batch


def test_m30_batch_is_cost_aware_and_bounded(tmp_path):
    result = compile_batch("M30", tmp_path, 1)
    assert result["decision"] == "PASS_CFX_BATCH_READY"
    assert len(result["projects"]) == 3
    for row in result["projects"].values():
        assert row["sq_genetic_shape"]["nominal_evaluations"] == 10000


def test_d1_funnel_has_exploratory_and_profiled_lanes(tmp_path):
    broad = compile_batch("D1", tmp_path / "broad", 1)
    profiled = compile_batch("D1", tmp_path / "profiled", 1, "profiled")
    assert broad["discovery_lane"] == "exploratory"
    assert len(broad["projects"]) == 3
    assert profiled["discovery_lane"] == "profiled"
    assert len(profiled["projects"]) == 6
    for batch in (broad, profiled):
        for row in batch["projects"].values():
            assert row["sq_genetic_shape"]["nominal_evaluations"] == 10000
