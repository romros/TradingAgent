import math

import pytest

from lab.sq_bridge.etf_twelve_one_post_oos_robustness_v1 import apply_costs, bootstrap


def test_costs_charge_only_actual_turnover():
    rows = [{"asset": "A", "gross_return": .01},
            {"asset": "A", "gross_return": .02},
            {"asset": "B", "gross_return": .03},
            {"asset": None, "gross_return": 0}]
    values = apply_costs(rows, 10)
    assert values == pytest.approx([.009, .02, .028, -.001])


def test_bootstrap_is_deterministic():
    first = bootstrap([.01, -.02, .03, .01], simulations=100)
    second = bootstrap([.01, -.02, .03, .01], simulations=100)
    assert first == second
    assert math.isfinite(first["drawdown_p95"])
