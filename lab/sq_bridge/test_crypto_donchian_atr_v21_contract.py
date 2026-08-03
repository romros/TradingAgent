import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from lab.sq_bridge.crypto_donchian_atr_v21 import entry_signal, simulate
from lab.sq_bridge.temporal_evidence_gate import evaluate


ROOT = Path(__file__).parent


def test_v21_grid_is_frozen_and_universal():
    config = json.loads((ROOT / "family_crypto_donchian_atr_v21.json").read_text())
    assert "asset" not in config["grid"]
    points = 1
    for key, values in config["grid"].items():
        if key != "points":
            points *= len(values)
    assert points == config["grid"]["points"] == 5184
    assert max(config["grid"]["hold_bars"]) * 4 == 48
    assert config["pre_registered_discovery_gate"]["minimum_positive_asset_ratio"] == 1.0


def test_v21_temporal_claim_is_internal_only():
    ledger = json.loads((ROOT / "temporal_evidence_ledger.json").read_text())
    proposal = json.loads((ROOT / "proposal_crypto_donchian_atr_v21.json").read_text())
    result = evaluate(ledger, proposal)
    assert result["decision"] == "PASS_INTERNAL_NON_INDEPENDENT"
    assert result["performance_promotion_authorized"] is False


def test_donchian_channel_excludes_signal_bar_high():
    index = pd.date_range("2022-01-03", periods=5, freq="4h", tz="UTC")
    base = pd.DataFrame({"open": [10, 10, 10, 10, 12], "high": [10, 10, 10, 10, 12],
                         "low": [9, 9, 9, 9, 11], "close": [10, 10, 10, 10, 12],
                         "atr": [1] * 5, "complete": [True] * 5}, index=index)
    params = {"side": "long", "session_start_utc": 16, "day_group": "weekday",
              "channel_bars": 3, "entry_buffer_atr": 0, "ema_regime_bars": 0}
    assert entry_signal(base, params).tolist() == [False, False, False, False, True]
    changed = base.copy(); changed.loc[index[-1], "high"] = 10_000
    assert entry_signal(changed, params).tolist() == [False, False, False, False, True]
    params["session_start_utc"] = 8
    assert not entry_signal(base, params).any()


def test_trailing_stop_from_bar_extreme_only_applies_next_bar():
    index = pd.date_range("2022-01-03", periods=3, freq="4h", tz="UTC")
    frame = pd.DataFrame({"open": [100, 100, 106], "high": [101, 110, 108],
                          "low": [99, 99, 106], "close": [100, 108, 107],
                          "atr": [2, 2, 2], "complete": [True] * 3}, index=index)
    params = {"asset": "BTCUSD", "side": "long", "stop_atr": 2.5,
              "trail_atr": 2.5, "hold_bars": 2}
    costs = {"opening_fee_bps_per_trade": 5, "oracle_fee_usdc_per_trade": 0.1,
             "scenarios": {"stress": {"dynamic_spread_and_impact_bps": 10,
                                        "annual_rollover_pct": 40}}}
    account = {"capital_usdc": 200, "risk_per_trade_pct": 1,
               "venue_max_leverage": {"BTCUSD": 200}, "liquidation_buffer_over_stop": 1.25,
               "maximum_margin_pct": 35}
    trades = simulate(frame, params, costs, account, prepared=np.array([True, False, False]))
    assert len(trades) == 1
    assert trades[0]["reason"] == "time"
    assert trades[0]["gross_underlying"] == pytest.approx(0.07)


def test_recorded_walk_forward_rejects_without_touching_holdout():
    path = ROOT / "evidence" / "crypto_donchian_atr_v21_walkforward.json"
    if not path.exists():
        pytest.skip("walk-forward evidence not generated in this checkout")
    result = json.loads(path.read_text())
    assert result["decision"] == "REJECT_CRYPTO_DONCHIAN_ATR_INTERNAL_WF"
    assert result["survivor_candidate_ids"] == []
    assert result["global_holdout_accessed"] is False
    assert result["sqcli_builder_executed"] is False
    assert result["paper_or_live_authorized"] is False
