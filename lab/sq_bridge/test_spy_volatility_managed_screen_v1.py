import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE_SPEC = importlib.util.spec_from_file_location("vol", HERE / "spy_volatility_managed_screen_v1.py")
vol = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(vol)


def test_preregistration_lock_and_sealed_oos():
    spec = vol.load_spec()
    assert spec["single_variant"] is True
    assert spec["holdout_2025"] == "SEALED_NOT_LOADED"


def test_validation_gate():
    gate = {"minimum_sessions": 2, "minimum_net_return": 0,
            "minimum_sharpe_improvement": .1,
            "maximum_drawdown_ratio_to_buy_and_hold": .85,
            "positive_calendar_years_required": 2}
    value = {"strategy": {"sessions": 2, "net_return": .1,
                           "sharpe_improvement": .2,
                           "drawdown_ratio_to_buy_and_hold": .5,
                           "positive_calendar_years": 2}}
    assert vol.passes(value, gate)
    value["strategy"]["sharpe_improvement"] = .05
    assert not vol.passes(value, gate)
