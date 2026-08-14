import tempfile
from pathlib import Path

import pytest

from lab.sq_bridge.equity_momentum_portfolio_v1 import load, simulate


def test_rejects_2025_filename_before_reading():
    with pytest.raises(ValueError, match="2025"):
        load(Path("missing_2025.csv"))


def test_rejects_2025_row():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "asset_2017_2024.csv"
        p.write_text("2025.01.02,00:00,1,1,1,1,0\n")
        with pytest.raises(ValueError, match="2025"):
            load(p)


def test_signal_close_enters_only_at_next_open():
    import datetime
    start = datetime.date(2020, 1, 1)
    days = [(start + datetime.timedelta(days=i)).isoformat() for i in range(400)]
    # A wins the ranking through closes, but its next open gaps from 2 to 20.
    # Correct next-open execution therefore cannot capture that gap.
    a, b = {}, {}
    for i, day in enumerate(days):
        a[day] = (1 + i / 100, 1 + i / 100)
        b[day] = (1.0, 1.0)
    signal = 259
    a[days[signal + 1]] = (20.0, 20.0)
    result, _ = simulate({"A": a, "B": b}, "return", 63,
                         "weekly_last_session", 1,
                         days[250], days[350], True)
    assert result["total_return"] < 5


def test_period_never_closes_outside_boundary():
    import datetime
    start = datetime.date(2020, 1, 1)
    days = [(start + datetime.timedelta(days=i)).isoformat() for i in range(500)]
    frames = {name: {day: (1 + i / scale, 1 + i / scale)
                     for i, day in enumerate(days)}
              for name, scale in (("A", 100), ("B", 200))}
    result, _ = simulate(frames, "return", 63, "monthly_last_session", 1,
                         "2020-10-01", "2020-12-31", True)
    assert set(result["calendar_years"]) == {"2020"}
