from pathlib import Path

import pytest

from lab.sq_bridge.sq_ostium_equity_parity import compare, load_sq_csv


def test_csv_loader_and_exact_comparison(tmp_path: Path):
    path=tmp_path/"sq.csv"; path.write_text(
        "Date,Time,Open,High,Low,Close,Volume\n"
        "2026.03.02,00:00,100,102,99,101,1\n"
        "2026.03.03,00:00,101,104,100,103,1\n")
    sq=load_sq_csv(path); result=compare(sq,[dict(row,bars=390) for row in sq])
    assert result["overlap_days"]==2
    assert result["ohlc"]["close"]["median_bps"]==0
    assert result["return_direction_match_ratio"]==1


def test_duplicate_and_invalid_ohlc_are_rejected(tmp_path: Path):
    duplicate=tmp_path/"duplicate.csv"; duplicate.write_text(
        "Date,Open,High,Low,Close\n2026.01.01,1,2,.5,1\n2026.01.01,1,2,.5,1\n")
    with pytest.raises(ValueError,match="DUPLICATE_DATE"):load_sq_csv(duplicate)
    invalid=tmp_path/"invalid.csv"; invalid.write_text(
        "Date,Open,High,Low,Close\n2026.01.01,1,.8,.5,1\n")
    with pytest.raises(ValueError,match="INVALID_OHLC"):load_sq_csv(invalid)
