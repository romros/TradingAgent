from pathlib import Path

from lab.sq_bridge.build_xauusd_m15_cache import fingerprint


def test_fingerprint_tracks_file_metadata(tmp_path: Path):
    path = tmp_path / "data.parquet"
    path.write_bytes(b"one")
    first = fingerprint([path])
    path.write_bytes(b"different")
    assert fingerprint([path]) != first
