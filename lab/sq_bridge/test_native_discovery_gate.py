from pathlib import Path

import pytest

from lab.sq_bridge.native_discovery_gate import freeze


def test_freeze_is_complete_and_refuses_overwrite(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "frozen"
    source.mkdir()
    (source / "b.sqx").write_bytes(b"b")
    (source / "a.sqx").write_bytes(b"a")
    paths = freeze(source, destination)
    assert [path.name for path in paths] == ["a.sqx", "b.sqx"]
    assert (destination / "a.sqx").read_bytes() == b"a"
    with pytest.raises(ValueError, match="FREEZE_DESTINATION_NOT_EMPTY"):
        freeze(source, destination)


def test_freeze_rejects_empty_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="NO_SQX"):
        freeze(source, tmp_path / "frozen")
