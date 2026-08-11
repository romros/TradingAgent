import csv
import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from lab.sq_bridge.eurusd_d1_holdout_extension_v4 import build


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path, mismatch=False):
    base = tmp_path / "base.csv"
    with base.open("w") as handle:
        for index in range(5001):
            day = (datetime(2000, 1, 3) + timedelta(days=index)).date()
            handle.write(f"{day:%Y.%m.%d},00:00,1.00000,1.20000,0.90000,1.10000,1\n")
    overlap_day = (datetime(2000, 1, 3) + timedelta(days=5000)).date()
    start = datetime.combine(overlap_day - timedelta(days=1), datetime.min.time(), timezone.utc)
    rows = []
    for offset in range(1368):
        stamp = int((start + timedelta(hours=22, minutes=offset)).timestamp())
        rows.append([stamp, 1.0 if not mismatch else 1.01, 1.2, .9, 1.1, 1])
    next_start = start + timedelta(days=1)
    for offset in range(1368):
        stamp = int((next_start + timedelta(hours=22, minutes=offset)).timestamp())
        rows.append([stamp, 1.1, 1.3, 1.0, 1.2, 1])
    cache = tmp_path / "duka.json.gz"
    with gzip.open(cache, "wt") as handle:
        json.dump(rows, handle)
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({
        "decision": "PASS_D1_SOURCE_MAPPING", "performance_accessed": False,
        "cache_receipts": {"mapping_dukascopy": {
            "path": str(cache), "sha256": _sha(cache)}}}))
    return base, mapping, overlap_day


def test_extends_only_from_frozen_matching_complete_sessions(tmp_path):
    base, mapping, overlap = _fixture(tmp_path)
    output, receipt = tmp_path / "extended.csv", tmp_path / "receipt.json"
    result = build(base_path=base, mapping_artifact_path=mapping,
                   output_path=output, receipt_path=receipt,
                   required_through=(overlap + timedelta(days=1)).isoformat())
    assert result["decision"] == "PASS_HOLDOUT_SOURCE_EXTENSION"
    assert result["overlap_sessions"] == 1
    assert result["output_rows"] == 5002
    assert result["performance_accessed"] is False
    with output.open() as handle:
        assert sum(1 for _ in csv.reader(handle)) == 5002


def test_rejects_extension_that_disagrees_with_overlap(tmp_path):
    base, mapping, overlap = _fixture(tmp_path, mismatch=True)
    with pytest.raises(ValueError, match="does not match"):
        build(base_path=base, mapping_artifact_path=mapping,
              output_path=tmp_path / "extended.csv",
              receipt_path=tmp_path / "receipt.json",
              required_through=(overlap + timedelta(days=1)).isoformat())


def test_excludes_every_session_after_frozen_holdout_end(tmp_path):
    base, mapping, overlap = _fixture(tmp_path)
    output = tmp_path / "extended.csv"
    result = build(base_path=base, mapping_artifact_path=mapping,
                   output_path=output, receipt_path=tmp_path / "receipt.json",
                   required_through=overlap.isoformat())
    assert result["last"] == overlap.isoformat()
    assert result["output_rows"] == 5001
    assert result["source_cutoff_policy"] == (
        "exclude_every_session_after_frozen_holdout_end")
