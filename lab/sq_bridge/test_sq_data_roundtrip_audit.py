from pathlib import Path

from lab.sq_bridge.sq_data_roundtrip_audit import audit


def test_roundtrip_reports_bounded_sq_rounding(tmp_path: Path):
    source = tmp_path / "source.csv"
    exported = tmp_path / "exported.csv"
    source.write_text("2026.06.01,00:00,100.04,101.06,99.94,100.96,3.76\n")
    exported.write_text("Date,Time,Open,High,Low,Close,Volume\n2026.06.01,00:00,100.0,101.1,99.9,101.0,3\n")
    result = audit(source, exported)
    assert result["decision"] == "PASS_SIGNAL_RESEARCH"
    assert result["exact_numeric_parity"] is False
    assert result["field_errors"]["high"]["max_absolute_error"] == "0.04"


def test_roundtrip_blocks_timestamp_loss(tmp_path: Path):
    source = tmp_path / "source.csv"
    exported = tmp_path / "exported.csv"
    source.write_text("2026.06.01,00:00,100,101,99,100,3\n")
    exported.write_text("Date,Time,Open,High,Low,Close,Volume\n2026.06.01,00:01,100,101,99,100,3\n")
    assert audit(source, exported)["decision"] == "BLOCK"
