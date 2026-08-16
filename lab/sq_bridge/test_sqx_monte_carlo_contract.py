import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.sqx_monte_carlo_contract import inspect


def _sqx(path: Path, count: int = 4, *, declared: int | None = None,
         max_change: int = 10, symbol: str = "EURUSD_DUKAS",
         timeframe: str = "H4") -> Path:
    target = path / "result.sqx"
    result = f'''<RobustnessResults><NumberOfSimulations>{declared or count}</NumberOfSimulations>
      <Symbol>{symbol}</Symbol><TimeFrame>{timeframe}</TimeFrame>
      <DateRange>2017.01.01 - 2025.07.31</DateRange>
      <Methods><Method>Randomize strategy parameters, with probability 10 % and max change {max_change} %</Method></Methods>
    </RobustnessResults>'''
    prefix = "Results/Main: EURUSD/H4"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(f"{prefix}/MonteCarloRetest_Results.xml", result)
        archive.writestr(f"{prefix}/RobustnessOriginalOrders.bin", "original")
        for index in range(count):
            archive.writestr(
                f"{prefix}/MonteCarloRetest_Simulation{index}Orders.bin",
                f"orders-{index}")
    return target


def test_inspects_exact_native_parameter_monte_carlo_members(tmp_path):
    result = inspect(_sqx(tmp_path), simulations=4,
                     probability_pct=10, max_change_pct=10)
    assert result["simulations"] == 4
    assert len(result["simulation_order_sha256"]) == 4
    assert result["all_simulation_orders_nonempty"] is True
    assert result["no_parameter_change_simulations"] == 0


def test_maps_unmodified_probability_attempts_to_original_orders(tmp_path):
    result = inspect(_sqx(tmp_path, count=3, declared=4), simulations=4,
                     probability_pct=10, max_change_pct=10)
    assert result["randomized_simulations_materialized"] == 3
    assert result["no_parameter_change_simulations"] == 1
    assert result["simulation_order_members"][-1].endswith(
        "RobustnessOriginalOrders.bin")


@pytest.mark.parametrize("kwargs", [
    {"count": 4, "max_change": 20},
])
def test_rejects_missing_runs_or_wrong_method(tmp_path, kwargs):
    with pytest.raises(ValueError, match="NATIVE_EVIDENCE"):
        inspect(_sqx(tmp_path, **kwargs), simulations=4,
                probability_pct=10, max_change_pct=10)


def test_real_academia_sqx_proves_native_layout_but_not_v4_count():
    path = Path("academia/runtime/build143-final-capability-tests/user/projects-mc-complete/ACADEMIA_MC_PARAMETERS/databanks/Validation/Strategy 4.1.133.sqx")
    if not path.is_file():
        pytest.skip("Academia runtime evidence not present")
    result = inspect(path, simulations=50, probability_pct=10, max_change_pct=20)
    assert result["simulations"] == 50
    with pytest.raises(ValueError, match="NATIVE_EVIDENCE"):
        inspect(path, simulations=1000, probability_pct=10, max_change_pct=10)
