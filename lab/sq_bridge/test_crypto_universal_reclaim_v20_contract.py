import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab.sq_bridge.crypto_universal_reclaim_v20 import _positive_ratio, schedule_portfolio, stable_selection, universal_reclaim_signals
from lab.sq_bridge.temporal_evidence_gate import evaluate


ROOT = Path(__file__).parent


def test_v20_grid_is_universal_and_frozen():
    config = json.loads((ROOT / "family_crypto_universal_reclaim_v20.json").read_text())
    assert "asset" not in config["grid"]
    points = 1
    for key, values in config["grid"].items():
        if key != "points": points *= len(values)
    assert points == config["grid"]["points"] == 3888
    assert config["pre_registered_discovery_gate"]["minimum_positive_asset_ratio"] == 1.0


def test_v20_is_internal_and_cannot_promote():
    ledger = json.loads((ROOT / "temporal_evidence_ledger.json").read_text())
    proposal = json.loads((ROOT / "proposal_crypto_universal_reclaim_v20.json").read_text())
    result = evaluate(ledger, proposal)
    assert result["decision"] == "PASS_INTERNAL_NON_INDEPENDENT"
    assert result["performance_promotion_authorized"] is False


def _shock_frame(scale: float) -> pd.DataFrame:
    index = pd.date_range("2022-01-03", periods=4, freq="h", tz="UTC")
    return pd.DataFrame({
        "open": np.array([100, 100, 98, 100]) * scale,
        "high": np.array([101, 101, 100, 101]) * scale,
        "low": np.array([99, 97, 97, 99]) * scale,
        "close": np.array([100, 98, 100, 100]) * scale,
        "atr": np.array([1, 1, 1, 1]) * scale,
        "complete": [True] * 4,
    }, index=index)


def test_atr_normalisation_is_price_scale_invariant():
    params = {"side": "long", "session_start_utc": 0, "day_group": "weekday",
              "shock_close_atr": 1.5, "range_atr": 2.0, "reclaim_hours": 2,
              "reclaim_fraction": 0.5}
    small = universal_reclaim_signals(_shock_frame(1), params)
    large = universal_reclaim_signals(_shock_frame(1000), params)
    assert small[0].tolist() == large[0].tolist() == [False, False, True, False]
    assert np.allclose(small[1][2], large[1][2] / 1000)


def test_scheduler_is_deterministic_and_caps_concurrency():
    trade = lambda entry, exit: {"entry": entry, "exit": exit, "stress": 0.01}
    accepted, skipped = schedule_portfolio({
        "SOLUSD": [trade("2022-01-01T01:00:00+00:00", "2022-01-01T04:00:00+00:00")],
        "ETHUSD": [trade("2022-01-01T01:00:00+00:00", "2022-01-01T03:00:00+00:00")],
        "BTCUSD": [trade("2022-01-01T01:00:00+00:00", "2022-01-01T02:00:00+00:00")],
    }, 2)
    assert [item["asset"] for item in accepted] == ["BTCUSD", "ETHUSD"]
    assert skipped == [{"asset": "SOLUSD", "entry": "2022-01-01T01:00:00+00:00", "reason": "concurrency_cap"}]


def test_positive_asset_ratio_uses_compounded_net_return():
    assert _positive_ratio({"BTC": {"net_return_pct": 1}, "ETH": {"net_return_pct": 0.1},
                            "SOL": {"net_return_pct": -0.1}}) == 2 / 3


def test_isolated_passing_points_are_not_stable():
    config = json.loads((ROOT / "family_crypto_universal_reclaim_v20.json").read_text())
    base = {key: values[0] for key, values in config["grid"].items() if key != "points"}
    rows = [{"candidate_id": "isolated", "parameters": base, "passes_point_gate": True}]
    stable, representatives = stable_selection(config, rows)
    assert stable == []
    assert representatives == []
    assert rows[0]["passing_orthogonal_neighbours"] == 0
