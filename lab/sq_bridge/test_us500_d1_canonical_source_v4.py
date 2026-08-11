import hashlib
import json
from datetime import date, timedelta

import pytest

from lab.sq_bridge.us500_d1_canonical_source_v4 import build


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value))
    return path


def _fixture(tmp_path, monkeypatch):
    source = tmp_path / "source.parquet"; source.write_bytes(b"source")
    coverage = _write(tmp_path / "coverage.json", {
        "decision": "PASS_HISTORICAL_COVERAGE", "performance_accessed": False,
        "source": {"sha256": _sha(source)},
        "selected_research_span": {"first": "2020-01-01", "last": "2022-12-31"},
        "historical_complete_observations": 500})
    mapping = _write(tmp_path / "mapping.json", {
        "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False})
    first = date(2020, 1, 1)
    rows = [(first + timedelta(days=index), 100, 102, 99, 101, 1000, 390)
            for index in range(500)]
    monkeypatch.setattr(
        "lab.sq_bridge.us500_d1_canonical_source_v4.extract",
        lambda *args: rows)
    return source, coverage, mapping


def test_builds_hash_bound_performance_blind_d1_source(tmp_path, monkeypatch):
    source, coverage, mapping = _fixture(tmp_path, monkeypatch)
    output, receipt = tmp_path / "us500.csv", tmp_path / "receipt.json"
    result = build(source_path=source, coverage_path=coverage, mapping_path=mapping,
                   output_path=output, receipt_path=receipt)
    assert result["decision"] == "PASS_CANONICAL_D1_SOURCE"
    assert result["rows"] == 500
    assert result["performance_accessed"] is False
    assert result["canonical_sha256"] == _sha(output)
    assert output.read_text().splitlines()[0].startswith("2020.01.01,00:00,100,")


def test_rejects_source_changed_after_coverage(tmp_path, monkeypatch):
    source, coverage, mapping = _fixture(tmp_path, monkeypatch)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="does not authorize"):
        build(source_path=source, coverage_path=coverage, mapping_path=mapping,
              output_path=tmp_path / "out", receipt_path=tmp_path / "receipt")


def test_rejects_row_inventory_different_from_coverage(tmp_path, monkeypatch):
    source, coverage, mapping = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "lab.sq_bridge.us500_d1_canonical_source_v4.extract", lambda *args: [])
    with pytest.raises(ValueError, match="differ from frozen coverage"):
        build(source_path=source, coverage_path=coverage, mapping_path=mapping,
              output_path=tmp_path / "out", receipt_path=tmp_path / "receipt")
