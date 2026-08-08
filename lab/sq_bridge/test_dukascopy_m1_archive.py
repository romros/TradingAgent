import lzma
import struct
from datetime import date

from dukascopy_m1_archive import decode, month_days


def test_month_days_handles_leap_year():
    assert len(month_days(2024, 2)) == 29


def test_decode_m1_record():
    record = struct.pack(">IIIIIf", 60, 125000, 125100, 124900, 125050, 2.5)
    rows = decode(lzma.compress(record, format=lzma.FORMAT_ALONE), "GBPUSD", date(2024, 1, 2))
    assert rows[0][1:5] == (1.25, 1.251, 1.249, 1.2505)
    assert rows[0][0] == 1704153660
