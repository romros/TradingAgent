import json
import hashlib
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_project_batch_v4 import compile_batch


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "lab/sq_bridge/evidence/crypto_h4_experiment_design_v4.json"
SEMANTICS = ROOT / "lab/sq_bridge/crypto_h4_signal_semantics_v4.json"
BTC = ROOT / "lab/sq_bridge/evidence/btcusd_alq_h4_sq_resource_v4.json"
ETH = ROOT / "lab/sq_bridge/evidence/ethusd_alq_h4_sq_resource_v4.json"
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_REPRO_SMOKE/project.cfx")
CANDIDATE = "alq4_0123456789abcdef"


def _selector(tmp_path, mechanism="channel_breakout"):
    momentum = mechanism == "time_series_momentum"
    hypothesis = ("btcusd_time_series_momentum_both_v4" if momentum else
                  "btcusd_channel_breakout_both_v4")
    profile = ("crypto_h4_time_series_momentum_v4" if momentum else
               "crypto_h4_channel_breakout_v4")
    first = {"indicator_period": 50, "shift": 1,
             "exit_after_bars": 10, "atr_stop_multiple": 2.0}
    second = {"indicator_period": 51, "shift": 1,
              "exit_after_bars": 10, "atr_stop_multiple": 2.25}
    third = {"indicator_period": 49, "shift": 1,
             "exit_after_bars": 11, "atr_stop_multiple": 2.0}
    if momentum:
        first["roc_threshold_pct"] = 2.0
        second["roc_threshold_pct"] = 2.5
        third["roc_threshold_pct"] = 2.0
    region = {"candidate_id": CANDIDATE,
        "campaign_id": "btcusd-h4-alquimia-v4",
        "hypothesis_id": hypothesis,
        "market": "BTCUSD", "mechanism": mechanism, "direction": "both",
        "profile": profile, "central_attempt": 1,
        "central_parameters": first,
        "member_attempts": [1, 2, 3], "member_parameters": {
            "1": first, "2": second, "3": third}}
    path = tmp_path / "selector.json"
    path.write_text(json.dumps({"decision": "PASS_STABLE_REGIONS",
        "replay_verified": True, "replay_receipt": {
            "replayed_unique_points": 3,
            "design_sha256": hashlib.sha256(DESIGN.read_bytes()).hexdigest(),
            "semantics_sha256": hashlib.sha256(SEMANTICS.read_bytes()).hexdigest(),
            "sources": {"BTCUSD": {}}, "costs": {"BTCUSD": {}},
            "chunks": {hypothesis: {}}},
        "selected_candidate_ids": [CANDIDATE], "selected_regions": [region],
        "validation_accessed": False, "oos_accessed": False,
        "holdout_accessed": False, "sqcli_started": False}))
    return path


def _compile(selector, output):
    return compile_batch(selector_path=selector, design_path=DESIGN,
        semantics_path=SEMANTICS, scaffold_path=SCAFFOLD,
        btc_resource_path=BTC, eth_resource_path=ETH, output_dir=output)


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_compiles_replay_selected_region_and_resumes(tmp_path):
    output = tmp_path / "batch"
    result = _compile(_selector(tmp_path), output)
    assert result["decision"] == "PASS_CRYPTO_CFX_BATCH_READY"
    assert result["sqcli_started"] is False
    assert result["python_parity_required"] is True
    assert result["strategy_promotion_authorized"] is False
    row = result["projects"][CANDIDATE]
    assert row["genetic_shape"] == [4, 100, 25]
    assert Path(row["cfx_path"]).is_file()
    (output / "crypto_h4_project_batch.json").unlink()
    resumed = _compile(tmp_path / "selector.json", output)
    assert resumed["projects"] == result["projects"]


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_completed_batch_fails_if_cfx_changes(tmp_path):
    output = tmp_path / "batch"
    result = _compile(_selector(tmp_path), output)
    with Path(result["projects"][CANDIDATE]["cfx_path"]).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="path/hash mismatch"):
        _compile(tmp_path / "selector.json", output)


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_compiles_source_verified_momentum_region(tmp_path):
    result = _compile(_selector(tmp_path, "time_series_momentum"), tmp_path / "batch")
    row = result["projects"][CANDIDATE]
    assert row["mechanism"] == "time_series_momentum"


@pytest.mark.skipif(not SCAFFOLD.is_file(), reason="real SQ 143 scaffold unavailable")
def test_refuses_untranslated_selected_family_before_creating_output(tmp_path):
    output = tmp_path / "batch"
    selector = _selector(tmp_path, "volatility_compression_breakout")
    with pytest.raises(ValueError, match="UNTRANSLATED_SELECTED_MECHANISMS"):
        _compile(selector, output)
    assert not output.exists()
