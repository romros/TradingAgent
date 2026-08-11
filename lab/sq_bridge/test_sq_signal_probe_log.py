from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from sq_signal_probe_log import convert
from test_sqx_extract import SETTINGS, STRATEGY


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path: Path):
    sqx = tmp_path / "candidate.sqx"
    with zipfile.ZipFile(sqx, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr("settings.xml", SETTINGS)
        archive.writestr("version.txt", "3")
    market = tmp_path / "market.csv"
    market.write_text(
        "2024.01.01,00:00,100,101,99,100,1\n"
        "2024.01.02,00:00,100,101,99,100,1\n")
    jar = tmp_path / "probe.jar"
    jar.write_bytes(b"probe")
    build = tmp_path / "build.json"
    build.write_text(json.dumps({
        "decision": "PASS_SIGNAL_PROBE_JAR",
        "production_sq_modified": False,
        "log_schema": "sq_strategy_time_long;signal_variable_uuid;boolean_0_or_1",
        "output_jar_path": str(jar),
        "output_jar_sha256": _sha(jar),
    }))
    return sqx, market, build


def _millis(value: str) -> int:
    import pandas as pd
    return int(pd.Timestamp(value, tz="UTC").timestamp() * 1000)


def _raw_rows(timestamp: int, long: int, short: int) -> list[str]:
    return [
        f"{timestamp};33333333-1111-2222-3333-333333333333;0",
        f"{timestamp};33333333-2222-2222-3333-333333333333;0",
        f"{timestamp};L;{long}", f"{timestamp};S;{short}",
    ]


def test_converts_complete_probe_log_and_binds_every_source(tmp_path: Path):
    sqx, market, build = _inputs(tmp_path)
    raw = tmp_path / "raw.log"
    raw.write_text("\n".join(
        _raw_rows(_millis("2024-01-01"), 1, 0)
        + _raw_rows(_millis("2024-01-02"), 0, 1)) + "\n")
    signals, receipt = tmp_path / "signals.csv", tmp_path / "receipt.json"

    result = convert(raw_log_path=raw, sqx_path=sqx, market_data_path=market,
                     build_receipt_path=build, time_unit="ms",
                     signals_path=signals,
                     scoped_market_path=tmp_path / "scoped.csv",
                     receipt_path=receipt)

    assert result["decision"] == "PASS_COMPLETE_SQ_SIGNAL_LOG"
    assert result["raw_rows"] == result["complete_rows_expected"] == 8
    assert result["true_entry_signals"] == 2
    assert result["sqx_sha256"] == _sha(sqx)
    assert signals.read_text().splitlines() == [
        "Timestamp;Direction", "2024-01-01T00:00:00Z;long",
        "2024-01-02T00:00:00Z;short"]


@pytest.mark.parametrize("mutation, message", [
    (lambda rows: rows[:-1], "cobertura"),
    (lambda rows: rows + [rows[-1]], "duplicada"),
    (lambda rows: rows[:-1] + [rows[-1].rsplit(";", 1)[0] + ";x"], "Boolea"),
])
def test_fails_closed_on_incomplete_duplicate_or_invalid_rows(
        tmp_path: Path, mutation, message: str):
    sqx, market, build = _inputs(tmp_path)
    raw = tmp_path / "raw.log"
    rows = _raw_rows(_millis("2024-01-01"), 1, 0)
    raw.write_text("\n".join(mutation(rows)) + "\n")
    with pytest.raises(ValueError, match=message):
        convert(raw_log_path=raw, sqx_path=sqx, market_data_path=market,
                build_receipt_path=build, time_unit="ms",
                signals_path=tmp_path / "signals.csv",
                scoped_market_path=tmp_path / "scoped.csv",
                receipt_path=tmp_path / "receipt.json")


def test_rejects_probe_bar_not_present_in_frozen_market(tmp_path: Path):
    sqx, market, build = _inputs(tmp_path)
    raw = tmp_path / "raw.log"
    raw.write_text("\n".join(_raw_rows(_millis("2025-01-01"), 1, 0)) + "\n")
    with pytest.raises(ValueError, match="fora de les candles"):
        convert(raw_log_path=raw, sqx_path=sqx, market_data_path=market,
                build_receipt_path=build, time_unit="ms",
                signals_path=tmp_path / "signals.csv",
                scoped_market_path=tmp_path / "scoped.csv",
                receipt_path=tmp_path / "receipt.json")
