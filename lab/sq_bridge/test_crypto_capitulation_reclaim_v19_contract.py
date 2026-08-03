import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.crypto_capitulation_reclaim_v19 import parameter_grid, reclaim_signals, simulate
from lab.sq_bridge.temporal_evidence_gate import evaluate


ROOT = Path(__file__).parent


def test_v19_grid_and_folds_are_frozen():
    config = json.loads((ROOT / "family_crypto_capitulation_reclaim_v19.json").read_text())
    points = 1
    for key, values in config["grid"].items():
        if key != "points": points *= len(values)
    assert points == config["grid"]["points"] == 11664
    assert [fold["id"] for fold in config["periods"]["internal_folds"]] == ["2023H1", "2023H2", "2024H1", "2024H2", "2025H1"]
    assert config["global_holdout_release_authorized"] is False


def test_v19_temporal_proposal_is_internal_only():
    ledger = json.loads((ROOT / "temporal_evidence_ledger.json").read_text())
    proposal = json.loads((ROOT / "proposal_crypto_capitulation_reclaim_v19.json").read_text())
    result = evaluate(ledger, proposal)
    assert result["decision"] == "PASS_INTERNAL_NON_INDEPENDENT"
    assert result["performance_promotion_authorized"] is False


def test_v19_generator_matches_frozen_grid():
    config = json.loads((ROOT / "family_crypto_capitulation_reclaim_v19.json").read_text())
    assert len(list(parameter_grid(config))) == 11664


def test_long_shock_requires_later_reclaim_and_keeps_shock_atr():
    index = pd.date_range("2022-01-03", periods=20, freq="h", tz="UTC")
    close = np.full(20, 100.0); close[16] = 97.0; close[17] = 99.5
    frame = pd.DataFrame({"open": close, "high": close + .5, "low": close - .5,
        "close": close, "complete": True, "atr": 1.0, "normalized_atr": .01}, index=index)
    frame.loc[index[16], ["high", "low"]] = [100.0, 96.0]
    params = {"side": "long", "session_start_utc": 16, "day_group": "weekday", "shock_return": .02,
        "range_atr": 1.5, "reclaim_hours": 2, "reclaim_fraction": .5}
    signals, shock_atr = reclaim_signals(frame, params)
    assert not signals[16]
    assert signals[17]
    assert shock_atr[17] == 1.0


def test_reclaim_after_registered_window_is_not_a_signal():
    index = pd.date_range("2022-01-03", periods=20, freq="h", tz="UTC")
    close = np.full(20, 100.0); close[16] = 97.0; close[17] = 97.5; close[18] = 99.5
    frame = pd.DataFrame({"open": close, "high": close + .5, "low": close - .5,
        "close": close, "complete": True, "atr": 1.0, "normalized_atr": .01}, index=index)
    frame.loc[index[16], ["high", "low"]] = [100.0, 96.0]
    params = {"side": "long", "session_start_utc": 16, "day_group": "weekday", "shock_return": .02,
        "range_atr": 1.5, "reclaim_hours": 1, "reclaim_fraction": .5}
    assert not reclaim_signals(frame, params)[0].any()


def test_trade_is_skipped_when_registered_holding_crosses_period_end():
    config = json.loads((ROOT / "family_crypto_capitulation_reclaim_v19.json").read_text())
    index = pd.date_range("2022-01-03", periods=10, freq="h", tz="UTC")
    frame = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
        "complete": True, "atr": 1.0, "normalized_atr": .01}, index=index)
    signals, signal_atr = np.zeros(10, dtype=bool), np.full(10, np.nan); signals[8], signal_atr[8] = True, 1.0
    params = {"asset": "BTCUSD", "side": "long", "stop_atr": 1.0, "hold_bars": 6}
    assert simulate(frame, params, config["cost_model"], config["small_account"], prepared=(signals, signal_atr)) == []
