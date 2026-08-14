import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.sqx_monte_carlo_partial_recovery import inspect_partial


def _fixture(path: Path, declared: int, persisted: int) -> None:
    result = (f"<Results><NumberOfSimulations>{declared}</NumberOfSimulations>"
              "<Method>Randomize strategy parameters, with probability 20 % "
              "and max change 10 %</Method></Results>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Results/Main: CAT/MonteCarloRetest_Results.xml", result)
        for index in range(persisted):
            archive.writestr(
                f"Results/Main: CAT/MonteCarloRetest_Simulation{index}Orders.bin",
                f"orders-{index}",
            )


def test_accepts_only_small_contiguous_trailing_gap(tmp_path):
    source = tmp_path / "partial.sqx"
    _fixture(source, 1006, 1001)
    result = inspect_partial(source, requested_simulations=1006,
                             probability_pct=20, max_change_pct=10)
    assert result["persisted_simulations"] == 1001
    assert result["missing_simulation_indices"] == list(range(1001, 1006))
    assert result["canonical_robustness_authorized"] is False


def test_rejects_complete_result(tmp_path):
    source = tmp_path / "complete.sqx"
    _fixture(source, 5, 5)
    with pytest.raises(ValueError, match="SAFE_TRAILING_BATCH"):
        inspect_partial(source, requested_simulations=5,
                        probability_pct=20, max_change_pct=10)
