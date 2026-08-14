import datetime as dt
import importlib.util
from pathlib import Path

P = Path(__file__).with_name("turn_of_month_screen_v1.py")
S = importlib.util.spec_from_file_location("tom", P)
M = importlib.util.module_from_spec(S); S.loader.exec_module(M)


def test_calendar_trade_uses_last_and_fourth_open():
    ds = [dt.date(2024, 1, 30), dt.date(2024, 1, 31), dt.date(2024, 2, 1),
          dt.date(2024, 2, 2), dt.date(2024, 2, 5), dt.date(2024, 2, 6)]
    frame = {d: (100 + i, 100 + i) for i, d in enumerate(ds)}
    got = M.trades(frame, dt.date(2024, 1, 1), dt.date(2024, 2, 29))
    assert got == [(dt.date(2024, 2, 6), 105 / 101 - 1)]


def test_period_boundary_requires_entry_and_exit_inside():
    ds = [dt.date(2023, 12, 29), dt.date(2024, 1, 2), dt.date(2024, 1, 3),
          dt.date(2024, 1, 4), dt.date(2024, 1, 5)]
    frame = {d: (100.0, 100.0) for d in ds}
    assert M.trades(frame, dt.date(2024, 1, 1), dt.date(2024, 12, 31)) == []


def test_2025_filename_rejected(tmp_path):
    p = tmp_path / "asset_2025.csv"; p.write_text("")
    try:
        M.load(p)
    except ValueError:
        return
    assert False
