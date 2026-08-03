import csv
import hashlib
import io
import zipfile

import pytest

from lab.sq_bridge.binance_sq_source import checksum_value, parse_archive, timestamp_ms


def archive(row):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as output:
        output.writestr("BTCUSDT-1m-2026-01.csv", row)
    return memory.getvalue()


def test_microseconds_and_milliseconds_normalize_to_ms():
    assert timestamp_ms("1735689600000000") == 1735689600000
    assert timestamp_ms("1735689600000") == 1735689600000


def test_archive_parses_valid_ohlcv_and_rejects_bad_high():
    content = archive("1735689600000000,100,102,99,101,5,1735689659999999,0,1,0,0,0\n")
    assert parse_archive(content)[0][:5] == (1735689600000, "100", "102", "99", "101")
    bad = archive("1735689600000000,100,99,98,101,5,1735689659999999,0,1,0,0,0\n")
    with pytest.raises(ValueError, match="INVALID_KLINE"): parse_archive(bad)


def test_checksum_file_parser():
    digest = hashlib.sha256(b"data").hexdigest()
    assert checksum_value(f"{digest}  file.zip\n".encode()) == digest
