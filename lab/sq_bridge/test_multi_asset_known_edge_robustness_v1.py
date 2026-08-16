from lab.sq_bridge.multi_asset_known_edge_robustness_v1 import percentile

def test_percentile_interpolates_deterministically():
    assert percentile([0, 10, 20], .5) == 10
    assert percentile([0, 10], .25) == 2.5
