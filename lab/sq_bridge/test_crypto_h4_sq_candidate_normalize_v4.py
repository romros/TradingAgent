from lab.sq_bridge.crypto_h4_sq_candidate_normalize_v4 import _nearest


def test_nearest_grid_is_decimal_deterministic_and_ties_choose_lower():
    assert _nearest(2.3, 1, 4, .25) == 2.25
    assert _nearest(2.375, 1, 4, .25) == 2.25
    assert _nearest(2.376, 1, 4, .25) == 2.5
