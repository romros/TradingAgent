import hashlib
import json

import pytest

from lab.sq_bridge.crypto_intraday_compression_checkpoint import build


def write(path, value):
    path.write_text(json.dumps(value))
    return path


def setup(tmp_path):
    config = {"family_id": "v18"}; config_path = write(tmp_path / "family.json", config)
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    source = {"BTCUSD": "a", "ETHUSD": "b", "SOLUSD": "c"}
    development = {"config_sha256": digest, "source_sha256": source, "stable_candidate_ids": ["one"],
        "topology_selected_representatives": [{"candidate_id": "one"}], "points_evaluated": 10,
        "point_gate_passes": 2, "validation_accessed": False, "holdout_accessed": False}
    validation = {"config_sha256": digest, "source_sha256": source, "decision": "REJECT_TEMPORAL_VALIDATION",
        "passing_candidate_ids": [], "results": [{"candidate_id": "one", "metrics": {"stress": {"trades": 3}}}],
        "holdout_accessed": False}
    return config_path, write(tmp_path / "dev.json", development), write(tmp_path / "val.json", validation)


def test_checkpoint_accepts_terminal_temporal_rejection(tmp_path):
    result = build(*setup(tmp_path))
    assert result["decision"] == "REJECT_CRYPTO_INTRADAY_COMPRESSION_NO_SQCLI"
    assert result["holdout_accessed"] is False


def test_checkpoint_rejects_any_validation_pass(tmp_path):
    paths = setup(tmp_path); validation = json.loads(paths[2].read_text()); validation["passing_candidate_ids"] = ["one"]
    paths[2].write_text(json.dumps(validation))
    with pytest.raises(ValueError, match="VALIDATION_NOT_TERMINAL_REJECTION"):
        build(*paths)
