from pathlib import Path

import pytest

from two_strategy_portfolio_v1 import load_cat, monthly_correlation


def test_rejects_2025_filename_before_read(tmp_path: Path):
    path = tmp_path / "CAT_2025.csv"
    path.write_text("date,open,high,low,close\n")
    with pytest.raises(ValueError, match="sealed"):
        load_cat([path])


def test_monthly_correlation_counts_inactive_as_zero():
    left = [{"date": "2024-01-02", "return": .1}, {"date": "2024-02-02", "return": -.1}]
    right = [{"date": "2024-01-05", "return": .1}, {"date": "2024-03-05", "return": .1}]
    result = monthly_correlation(left, right)
    assert result["months"] == 3
    assert result["correlation_zero_when_inactive"] == pytest.approx(.866025, abs=1e-6)
