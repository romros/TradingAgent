from pathlib import Path

from lab.sq_bridge.ostium_native_coverage_audit import audit_symbol


def _write(root: Path, rows: list[str]):
    root.mkdir(parents=True)
    (root / "sample.csv").write_text("\n".join(rows) + "\n")


def test_continuous_price_jump_blocks_native_sample(tmp_path):
    root = tmp_path / "MSFT"
    _write(root, ["1704205800,100,101,99,100,0", "1704205860,100,120,99,120,0"])
    result = audit_symbol("MSFT", root, "us_equity")
    assert result["integrity_ok"] is False
    assert len(result["continuous_return_outliers"]) == 1


def test_overnight_jump_is_not_a_continuous_minute_outlier(tmp_path):
    root = tmp_path / "MSFT"
    _write(root, ["1704205800,100,101,99,100,0", "1704292200,120,121,119,120,0"])
    result = audit_symbol("MSFT", root, "us_equity")
    assert result["continuous_return_outliers"] == []


def test_duplicate_and_invalid_ohlc_are_counted(tmp_path):
    root = tmp_path / "NDXUSD"
    _write(root, ["1704205800,100,99,101,100,0", "1704205800,100,101,99,100,0"])
    result = audit_symbol("NDXUSD", root, "index")
    assert result["duplicate_timestamps"] == 1
    assert result["invalid_ohlc_rows"] == 1
    assert result["decision"] == "BLOCK_NATIVE_INTEGRITY_OR_COVERAGE"
