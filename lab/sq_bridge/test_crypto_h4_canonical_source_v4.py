import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from lab.sq_bridge.crypto_h4_canonical_source_v4 import aggregate, build


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(path, minutes=240 * 365 * 6 * 5, skip=frozenset()):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with path.open("w") as handle:
        for index in range(minutes):
            if index in skip:
                continue
            stamp = start + timedelta(minutes=index)
            handle.write(f"{stamp:%Y.%m.%d},{stamp:%H:%M},100,102,99,101,1\n")
    return start


def _manifest(path, source, rows, first, last, gaps=0, missing=0):
    archive = path.parent / "archive.zip"
    archive.write_bytes(b"official monthly source")
    value = {
        "source": "Binance official public spot monthly klines",
        "symbol": "BTCUSDT", "timeframe": "M1", "timezone": "UTC",
        "rows": rows, "first_utc": first.isoformat(), "last_utc": last.isoformat(),
        "continuity": {"gap_intervals": gaps, "missing_minutes": missing},
        "output_sha256": _sha(source), "research_authorized": False,
        "paper_or_live_authorized": False,
        "sources": [{"archive": str(archive), "sha256": _sha(archive)}],
    }
    path.write_text(json.dumps(value))
    return path


def test_aggregate_keeps_only_exact_utc_h4_buckets(tmp_path):
    source = tmp_path / "m1.csv"
    start = _source(source, minutes=480, skip={17})
    bars, inventory = aggregate(source)
    assert len(bars) == 1
    assert bars[0][0] == start + timedelta(hours=4)
    assert inventory["missing_minutes"] == 1
    assert inventory["gap_intervals"] == 1


def test_build_is_hash_bound_and_remains_research_blocked(tmp_path, monkeypatch):
    source = tmp_path / "m1.csv"
    minutes = 240
    first = _source(source, minutes=minutes)
    last = first + timedelta(hours=4 * 365 * 6 * 5) - timedelta(minutes=1)
    manifest = _manifest(tmp_path / "manifest.json", source, minutes, first, last)
    bars = [(first + timedelta(hours=4 * index), 100, 102, 99, 101, 240)
            for index in range(365 * 6 * 5)]
    monkeypatch.setattr(
        "lab.sq_bridge.crypto_h4_canonical_source_v4.aggregate",
        lambda _: (bars, {"rows": minutes, "first_utc": first.isoformat(),
                          "last_utc": last.isoformat(), "gap_intervals": 0,
                          "missing_minutes": 0}))
    result = build(source_path=source, manifest_path=manifest,
                   output_path=tmp_path / "h4.csv", receipt_path=tmp_path / "receipt.json")
    assert result["coverage_ratio"] == 1
    assert result["rows"] == 365 * 6 * 5
    assert result["research_authorized"] is False
    assert result["proxy_mapping_required"] is True
    assert (tmp_path / "h4.csv").read_text().splitlines()[0].startswith(
        "2020.01.01,00:00,100.000000,102.000000,99.000000,101.000000,240.000000")


def test_build_rejects_changed_source(tmp_path):
    source = tmp_path / "m1.csv"
    first = _source(source, minutes=12)
    manifest = _manifest(tmp_path / "manifest.json", source, 12, first,
                         first + timedelta(minutes=11))
    source.write_text(source.read_text() + "2020.01.01,00:12,100,102,99,101,1\n")
    with pytest.raises(ValueError, match="does not authorize"):
        build(source_path=source, manifest_path=manifest,
              output_path=tmp_path / "out", receipt_path=tmp_path / "receipt")


def test_aggregate_rejects_duplicates(tmp_path):
    source = tmp_path / "m1.csv"
    source.write_text("2020.01.01,00:00,100,102,99,101,1\n" * 2)
    with pytest.raises(ValueError, match="duplicate or unordered"):
        aggregate(source)
