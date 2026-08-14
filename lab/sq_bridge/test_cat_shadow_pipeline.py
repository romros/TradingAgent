import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from apps.cat_shadow_pipeline import verify_forward


def fixture(tmp_path: Path, **changes):
    csv = tmp_path / "cat.csv"; csv.write_text("date,open,high,low,close\n2026-08-13,1,1,1,1\n")
    receipt = {"classification": "FORWARD_ONLY_NOT_RESEARCH",
               "csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
               "performance_calculated": False, "last_session": "2026-08-13", "sessions": 45}
    receipt.update(changes)
    path = tmp_path / "receipt.json"; path.write_text(json.dumps(receipt))
    return csv, path


def test_verifies_bound_forward_receipt(tmp_path: Path):
    csv, receipt = fixture(tmp_path)
    assert verify_forward(csv, receipt, dt.date(2026, 8, 14))["sessions"] == 45


def test_rejects_hash_mismatch(tmp_path: Path):
    csv, receipt = fixture(tmp_path, csv_sha256="bad")
    with pytest.raises(ValueError, match="hash"):
        verify_forward(csv, receipt, dt.date(2026, 8, 14))


def test_rejects_stale_feed(tmp_path: Path):
    csv, receipt = fixture(tmp_path, last_session="2026-08-01")
    with pytest.raises(ValueError, match="stale"):
        verify_forward(csv, receipt, dt.date(2026, 8, 14))
