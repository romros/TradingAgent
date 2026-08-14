import csv
from pathlib import Path

import pytest

from lab.sq_bridge.ko_pep_pairs_screen_v1 import load_bars, validation_passes


def test_2025_filename_is_sealed(tmp_path: Path):
    path = tmp_path / "prices_2025.csv"
    path.write_text("date,open,close\n2024-01-02,1,1\n")
    with pytest.raises(ValueError, match="filename"):
        load_bars(path)


def test_2025_row_is_sealed(tmp_path: Path):
    path = tmp_path / "prices.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("date", "open", "close"))
        writer.writerow(("2025-01-02", 1, 1))
    with pytest.raises(ValueError, match="row date"):
        load_bars(path)


def test_stage_ceiling_does_not_load_oos(tmp_path: Path):
    path = tmp_path / "prices.csv"
    path.write_text("date,open,close\n2023-12-29,1,1\n2024-01-02,99,99\n")
    bars = load_bars(path, __import__("datetime").date(2023, 12, 31))
    assert len(bars) == 1


def test_validation_gate_is_conjunctive():
    good = {"closed_pairs": 20, "profit_factor": 1.15, "net_return_pct": 0.01,
            "maximum_mark_to_market_drawdown_pct": 20.0, "positive_halves": 3}
    assert validation_passes(good)
    for key in good:
        bad = dict(good)
        bad[key] = {"closed_pairs": 19, "profit_factor": 1.14, "net_return_pct": 0,
                    "maximum_mark_to_market_drawdown_pct": 20.01, "positive_halves": 2}[key]
        assert not validation_passes(bad)
