import lzma
import struct
from datetime import date
from pathlib import Path

from dukascopy_m1_archive import (
    build_month,
    daily_cache_path,
    decode,
    is_fx_symbol,
    month_days,
    nyse_closed_dates,
    partition_path,
    read_daily_cache,
    write_daily_cache,
)


def test_month_days_handles_leap_year():
    assert len(month_days(2024, 2)) == 29
    assert sum(day.weekday() < 5 for day in month_days(2024, 2)) == 21


def test_decode_m1_record():
    record = struct.pack(">IIIIIf", 60, 125000, 125100, 124900, 125050, 2.5)
    rows = decode(lzma.compress(record, format=lzma.FORMAT_ALONE), "GBPUSD", date(2024, 1, 2))
    assert rows[0][1:5] == (1.25, 1.251, 1.249, 1.2505)
    assert rows[0][0] == 1704153660


def test_decode_stock_uses_explicit_catalog_scale():
    record = struct.pack(">IIIIIf", 60, 250125, 251000, 249500, 250750, 10.0)
    rows = decode(lzma.compress(record, format=lzma.FORMAT_ALONE),
                  "CATUSUSD", date(2024, 1, 2), price_scale=1000)
    assert rows[0][1:5] == (250.125, 251.0, 249.5, 250.75)


def test_stock_vendor_symbol_is_not_misclassified_as_fx():
    assert is_fx_symbol("EURUSD")
    assert not is_fx_symbol("CATUSUSD")


def test_daily_cache_is_atomic_and_round_trips(tmp_path: Path):
    day = date(2024, 1, 2)
    path = daily_cache_path(tmp_path, "CATUSUSD", day)
    rows = [(1704153660, 250.125, 251.0, 249.5, 250.75, 10.0)]
    write_daily_cache(path, rows)
    assert read_daily_cache(path) == rows
    assert not path.with_suffix(".tmp.gz").exists()


def test_nyse_calendar_handles_recurring_and_exceptional_closures():
    assert date(2017, 7, 4) in nyse_closed_dates(2017)
    assert date(2017, 4, 14) in nyse_closed_dates(2017)  # Good Friday
    assert date(2018, 12, 5) in nyse_closed_dates(2018)  # Bush funeral
    assert date(2022, 6, 20) in nyse_closed_dates(2022)  # Juneteenth observed
    assert date(2021, 6, 18) not in nyse_closed_dates(2021)
    assert date(2021, 12, 31) in nyse_closed_dates(2021)


def test_complete_manifest_with_wrong_hash_is_rebuilt(tmp_path: Path, monkeypatch):
    day = date(2024, 1, 2)
    rows = [(1704153660, 250.125, 251.0, 249.5, 250.75, 10.0)]
    write_daily_cache(daily_cache_path(tmp_path, "CATUSUSD", day), rows)
    target = partition_path(tmp_path, "CATUSUSD", 2024, 1)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"stale")
    target.with_name("manifest.json").write_text('{"status":"complete","sha256":"wrong"}\n')
    monkeypatch.setattr("dukascopy_m1_archive.month_days", lambda year, month: [day])
    receipt = build_month(tmp_path, "CATUSUSD", 2024, 1, workers=1,
                          price_scale=1000, closed_dates=set())
    assert receipt["action"] == "written"
    assert receipt["sha256"] != "wrong"
    partition_path,
