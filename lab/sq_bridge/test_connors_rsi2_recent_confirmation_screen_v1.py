import importlib.util
from pathlib import Path


PATH = Path(__file__).with_name("connors_rsi2_recent_confirmation_screen_v1.py")
SPEC = importlib.util.spec_from_file_location("connors_recent", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_loader_supports_sq_and_header_csv_without_using_rows_after_end(tmp_path):
    end = MODULE.date(2025, 1, 2)
    sq = tmp_path / "sq.csv"
    sq.write_text("2025.01.02,00:00,10,11,9,10.5,1\n2025.01.03,00:00,99,99,99,99,1\n")
    header = tmp_path / "header.csv"
    header.write_text("date,open,high,low,close,volume,minutes\n2025-01-02,10,11,9,10.5,1,390\n2025-01-03,99,99,99,99,1,390\n")
    assert MODULE.load(sq, end) == [(end, 10.0, 10.5)]
    assert MODULE.load(header, end) == [(end, 10.0, 10.5)]
