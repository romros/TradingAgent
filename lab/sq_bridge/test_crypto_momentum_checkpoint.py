import json

import pytest

from lab.sq_bridge.crypto_momentum_checkpoint import build


def put(path, value):
    path.write_text(json.dumps(value))
    return path


def fixtures(tmp_path):
    hashes = {"BTCUSD": "btc", "ETHUSD": "eth", "SOLUSD": "sol"}
    manifests = {asset: put(tmp_path / f"{asset}.json", {"output_sha256": digest}) for asset, digest in hashes.items()}
    terminal = {"source_sha256": hashes, "stable_candidate_ids": [], "points_evaluated": 1,
                "point_gate_passes": 0, "oos_accessed": False, "holdout_accessed": False}
    v15 = put(tmp_path / "v15.json", terminal)
    v16 = put(tmp_path / "v16.json", terminal)
    v17 = put(tmp_path / "v17.json", {**terminal, "stable_candidate_ids": ["x"], "point_gate_passes": 1})
    validation = put(tmp_path / "validation.json", {"source_sha256": hashes, "decision": "REJECT_TEMPORAL_VALIDATION",
        "passing_candidate_ids": [], "oos_accessed": False, "holdout_accessed": False})
    def roundtrip(asset):
        return put(tmp_path / f"rt-{asset}.json", {"source_sha256": hashes[asset], "decision": "PASS_SIGNAL_RESEARCH",
            "source_rows": 43200, "exported_rows": 43200, "timestamps_exact_and_ordered": True,
            "field_errors": {field: {"changed_rows": 0} for field in ("open", "high", "low", "close")},
            "paper_or_live_authorized": False})
    return manifests, v15, v16, v17, validation, {"ETHUSD": roundtrip("ETHUSD"), "SOLUSD": roundtrip("SOLUSD")}


def test_build_accepts_terminal_rejection_and_signal_safe_roundtrips(tmp_path):
    args = fixtures(tmp_path)
    result = build(*args)
    assert result["decision"] == "REJECT_CRYPTO_MOMENTUM_NO_OOS_NO_SQCLI"
    assert result["sq_signal_sources"] == {"ETHUSD": "PASS_SIGNAL_RESEARCH", "SOLUSD": "PASS_SIGNAL_RESEARCH"}


def test_build_rejects_changed_ohlc(tmp_path):
    args = fixtures(tmp_path)
    sol = json.loads(args[-1]["SOLUSD"].read_text())
    sol["field_errors"]["close"]["changed_rows"] = 1
    args[-1]["SOLUSD"].write_text(json.dumps(sol))
    with pytest.raises(ValueError, match="ROUNDTRIP_NOT_SIGNAL_SAFE:SOLUSD"):
        build(*args)
