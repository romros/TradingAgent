import json

import pytest

from lab.sq_bridge.eurusd_v4_real_scaffold_smoke import smoke


def test_smoke_fails_before_compilation_when_worker_does_not_bind_inputs(tmp_path):
    scaffold = tmp_path / "scaffold.cfx"
    source = tmp_path / "source.csv"
    registry = tmp_path / "registry.json"
    methodology = tmp_path / "methodology.json"
    config = tmp_path / "worker.json"
    scaffold.write_bytes(b"not opened")
    source.write_text("not read")
    registry.write_text(json.dumps({"markets": {"EURUSD": {}}}))
    methodology.write_text("{}")
    config.write_text(json.dumps({
        "schema_version": 1,
        "scaffold_path": str(tmp_path / "different.cfx"),
        "scaffold_sha256": "0" * 64,
        "scaffold_sq_version": "143.2708",
        "registry_sha256": "0" * 64,
    }))

    with pytest.raises(ValueError, match="does not bind"):
        smoke(
            scaffold_path=scaffold, source_path=source,
            registry_path=registry, methodology_path=methodology,
            worker_config_path=config)
