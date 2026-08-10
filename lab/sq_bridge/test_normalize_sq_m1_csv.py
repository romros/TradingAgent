import csv
import tempfile
from pathlib import Path

import pytest

from normalize_sq_m1_csv import normalize


def test_normalizes_fixed_broker_offset_and_audits():
    pytest.importorskip("duckdb")
    with tempfile.TemporaryDirectory() as tmp:
        source, output, receipt = Path(tmp)/"input.csv", Path(tmp)/"out.parquet", Path(tmp)/"receipt.json"
        with source.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["2023.01.02", "17:00", 1.2, 1.3, 1.1, 1.25, 10])
            writer.writerow(["2023.01.02", "17:01", 1.25, 1.26, 1.2, 1.22, 11])
        result = normalize(source, output, receipt, broker_utc_offset_hours=-5)
        assert result["first_ts_utc"] == "2023-01-02T22:00:00+00:00"
        assert result["rows"] == 2 and result["duplicate_timestamps"] == 0
        assert result["invalid_ohlc"] == 0 and output.exists()


def test_normalizes_new_york_with_dst():
    pytest.importorskip("duckdb")
    with tempfile.TemporaryDirectory() as tmp:
        source, output, receipt = Path(tmp)/"input.csv", Path(tmp)/"out.parquet", Path(tmp)/"receipt.json"
        source.write_text("2023.01.02,17:00,1.2,1.3,1.1,1.25,10\n2023.07.03,17:00,1.2,1.3,1.1,1.25,10\n")
        result = normalize(source, output, receipt, source_timezone="America/New_York")
        import duckdb
        timestamps = [row[0] for row in duckdb.connect().execute(
            "SELECT ts FROM read_parquet(?) ORDER BY ts", [str(output)]).fetchall()]
        assert timestamps == [1672696800, 1688418000]
        assert "DST rules" in result["normalization"]


def test_normalizes_broker_clock_seven_hours_ahead_of_new_york():
    pytest.importorskip("duckdb")
    with tempfile.TemporaryDirectory() as tmp:
        source, output, receipt = Path(tmp)/"input.csv", Path(tmp)/"out.parquet", Path(tmp)/"receipt.json"
        source.write_text("2026.03.08,08:59,1,1,1,1,1\n2026.03.08,10:00,1,1,1,1,1\n")
        result = normalize(source, output, receipt, source_timezone="America/New_York+07")
        import duckdb
        timestamps = [row[0] for row in duckdb.connect().execute(
            "SELECT ts FROM read_parquet(?) ORDER BY ts", [str(output)]).fetchall()]
        assert timestamps == [1772953140, 1772953200]
        assert "New_York+07" in result["source_timezone"]


def test_normalizes_helsinki_winter_and_summer_offsets():
    pytest.importorskip("duckdb")
    with tempfile.TemporaryDirectory() as tmp:
        source, output, receipt = Path(tmp)/"input.csv", Path(tmp)/"out.parquet", Path(tmp)/"receipt.json"
        source.write_text("2026.01.05,00:00,1,1,1,1,1\n2026.07.06,00:00,1,1,1,1,1\n")
        result = normalize(source, output, receipt, source_timezone="Europe/Helsinki")
        import duckdb
        timestamps = [row[0] for row in duckdb.connect().execute(
            "SELECT ts FROM read_parquet(?) ORDER BY ts", [str(output)]).fetchall()]
        assert timestamps == [1767564000, 1783285200]
        assert "EET/EEST" in result["normalization"]
