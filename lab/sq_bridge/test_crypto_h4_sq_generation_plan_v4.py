import json
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_sq_generation_plan_v4 import compile_plan


ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "lab/sq_bridge/evidence/crypto_h4_experiment_design_v4.json"
SEMANTICS = ROOT / "lab/sq_bridge/crypto_h4_signal_semantics_v4.json"
RESOURCE = ROOT / "lab/sq_bridge/evidence/btcusd_alq_h4_sq_resource_v4.json"


def _selector(tmp_path, replay=True):
    region = {"candidate_id": "alq4_test", "campaign_id": "btcusd-h4-alquimia-v4",
              "hypothesis_id": "btcusd_channel_breakout_long_v4", "market": "BTCUSD",
              "mechanism": "channel_breakout", "direction": "long",
              "profile": "crypto_h4_channel_breakout_v4", "central_attempt": 1,
              "central_parameters": {"indicator_period": 50, "shift": 1,
                                     "exit_after_bars": 10, "atr_stop_multiple": 2.0},
              "member_attempts": [1, 2, 3], "member_parameters": {
                  "1": {"indicator_period": 50, "shift": 1,
                        "exit_after_bars": 10, "atr_stop_multiple": 2.0},
                  "2": {"indicator_period": 51, "shift": 1,
                        "exit_after_bars": 10, "atr_stop_multiple": 2.25},
                  "3": {"indicator_period": 49, "shift": 1,
                        "exit_after_bars": 11, "atr_stop_multiple": 2.0}}}
    path = tmp_path / "selector.json"
    path.write_text(json.dumps({"decision": "PASS_STABLE_REGIONS",
        "replay_verified": replay, "replay_receipt": {"sha256": "a" * 64},
        "selected_regions": [region], "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False}))
    return path


def test_compiles_replayed_region_to_small_account_genetic_plan(tmp_path):
    result = compile_plan(selector_path=_selector(tmp_path), candidate_id="alq4_test",
        design_path=DESIGN, semantics_path=SEMANTICS, sq_resource_path=RESOURCE,
        output_path=tmp_path / "plan.json")
    assert result["decision"] == "PASS_SQ_PLAN_READY"
    assert result["initial_capital_usdc"] == 200
    assert result["discovery_leverage"] == 1
    assert result["money_management"] == {
        "method": "CryptoSizeByPrice", "use_account_balance": False,
        "maximum_size": 100, "decimals": 4,
        "fallback_to_size_one_allowed": False}
    assert result["attempt_budget"] == 10_000
    assert result["sq_genetic_shape"]["nominal_evaluations"] == 10_000
    assert result["parameter_search_space"]["indicator_period"] == {
        "minimum": 49, "maximum": 51, "allowed_values": [49, 50, 51]}
    assert result["maximum_promoted_candidates"] == 1
    assert result["sqcli_authorized"] is False


def test_refuses_region_without_deterministic_replay(tmp_path):
    with pytest.raises(ValueError, match="not replay verified"):
        compile_plan(selector_path=_selector(tmp_path, False), candidate_id="alq4_test",
            design_path=DESIGN, semantics_path=SEMANTICS, sq_resource_path=RESOURCE,
            output_path=tmp_path / "plan.json")
