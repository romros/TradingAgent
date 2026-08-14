import csv
from pathlib import Path

import pytest

from lab.sq_bridge.ibkr_equity_d1_canonical_v2 import build


def _source(path: Path, minutes: int = 390) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", "open", "high", "low", "close", "volume", "minutes"])
        writer.writerow(["2020-01-02", 100, 102, 99, 101, 5, minutes])
        writer.writerow(["2020-01-03", 101, 103, 100, 102, 6, 390])


def test_build_is_performance_blind_and_sq_canonical(tmp_path: Path):
    source, output, receipt = tmp_path / "in.csv", tmp_path / "out.csv", tmp_path / "r.json"
    _source(source)
    result = build(source, output, receipt, "CAT", "https://example.test/splits")
    assert result["decision"] == "PASS_CANONICAL_SOURCE_ONLY"
    assert result["performance_accessed"] is False
    assert output.read_text().splitlines()[0] == "2020.01.02,00:00,100.000000,102.000000,99.000000,101.000000,5.000000"


def test_build_rejects_incomplete_session(tmp_path: Path):
    source = tmp_path / "in.csv"
    _source(source, 389)
    with pytest.raises(ValueError, match="complete RTH"):
        build(source, tmp_path / "out.csv", tmp_path / "r.json", "CAT",
              "https://example.test/splits")


def test_build_repairs_provider_ohlc_envelope(tmp_path: Path):
    source, output = tmp_path / "in.csv", tmp_path / "out.csv"
    with source.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", "open", "high", "low", "close", "volume", "minutes"])
        writer.writerow(["2020-01-02", 102, 101, 100, 99, 5, 390])
    result = build(source, output, tmp_path / "r.json", "CAT", "https://example.test/splits")
    assert result["ohlc_envelope_repair"]["rows_repaired"] == 1
    assert output.read_text().split(",")[3:6] == ["102.000000", "99.000000", "99.000000"]
