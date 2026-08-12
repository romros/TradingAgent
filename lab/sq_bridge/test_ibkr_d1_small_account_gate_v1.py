from lab.sq_bridge.ibkr_d1_small_account_gate_v1 import minimum_capital


def test_minimum_capital_uses_largest_constraint():
    result = minimum_capital({
        "worst_observed_mae_usd": -300,
        "approximate_maximum_initial_margin_usd": 900,
        "mc_drawdown_p95_usd": 1000,
    })
    assert result["constraint_floors_usd"] == {
        "observed_mae": 20000.0,
        "initial_margin": 1500.0,
        "mc_drawdown_p95": 4000.0,
    }
    assert result["minimum_capital_usd"] == 20000.0
    assert result["controlling_constraint"] == "observed_mae"


def test_minimum_capital_can_be_mc_controlled():
    result = minimum_capital({
        "worst_observed_mae_usd": -15,
        "approximate_maximum_initial_margin_usd": 600,
        "mc_drawdown_p95_usd": 750,
    })
    assert result["minimum_capital_usd"] == 3000.0
    assert result["controlling_constraint"] == "mc_drawdown_p95"
