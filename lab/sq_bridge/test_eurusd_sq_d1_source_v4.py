from datetime import date, timedelta

import pytest

from lab.sq_bridge.eurusd_sq_d1_source_v4 import validate, write_csv


def rows(count=5000):
    result, day = [], date(2000, 1, 3)
    while len(result) < count:
        if day.weekday() < 5:
            result.append((day, 1440, 1.1, 1.2, 1.0, 1.15, 100.4))
        day += timedelta(days=1)
    return result


def test_writes_deterministic_mt4_d1_without_weekends(tmp_path):
    target = tmp_path / "eurusd.csv"
    write_csv(target, rows())
    lines = target.read_text().splitlines()
    assert len(lines) == 5000
    assert lines[0] == "2000.01.03,00:00,1.10000,1.20000,1.00000,1.15000,100"
    assert target.read_bytes().endswith(b"\n")


def test_rejects_sunday_or_incomplete_session():
    invalid = rows()
    invalid[0] = (date(2000, 1, 2), 1440, 1.1, 1.2, 1.0, 1.15, 100)
    with pytest.raises(ValueError, match="weekend"):
        validate(invalid)
    invalid = rows()
    invalid[0] = (invalid[0][0], 100, 1.1, 1.2, 1.0, 1.15, 100)
    with pytest.raises(ValueError, match="incomplete"):
        validate(invalid)
