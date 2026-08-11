import json

import pytest

from lab.sq_bridge.eurusd_v4_hypotheses import EURUSD_PROFILE_BLOCKS
from lab.sq_bridge.eurusd_v4_real_scaffold_smoke import (
    smoke, verify_translation_surface,
)


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


def test_all_preregistered_profiles_have_an_exact_runtime_surface():
    result = verify_translation_surface(EURUSD_PROFILE_BLOCKS)
    assert result["profile_count"] == 3
    assert result["extractor_runtime_signal_surfaces_equal"] is True
    assert result["unknown_action_parameters_rejected"] is True


def test_translation_surface_rejects_an_unmapped_future_block():
    profiles = {name: set(blocks) for name, blocks in EURUSD_PROFILE_BLOCKS.items()}
    profiles["eurusd_d1_breakout_v4"].add("Indicators.FutureOracle")
    with pytest.raises(ValueError, match="escapes"):
        verify_translation_surface(profiles)
