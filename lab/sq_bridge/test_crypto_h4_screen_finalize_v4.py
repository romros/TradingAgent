import json
from pathlib import Path

import pytest

from lab.sq_bridge.crypto_h4_screen_finalize_v4 import finalize, replay_regions
from lab.sq_bridge.crypto_h4_screen_worker_v4 import _compact
from lab.sq_bridge.crypto_h4_train_engine_v4 import evaluate_point
from lab.sq_bridge.test_crypto_h4_train_engine_v4 import _bars, _channel_params


def _write(path, value): path.write_text(json.dumps(value)); return path


def test_global_finalize_waits_before_touching_missing_inputs_or_state(tmp_path):
    btc = _write(tmp_path / "btc.json", {"decision": "BLOCK",
        "blocking_reasons": ["BTC_MAPPING"]})
    eth = _write(tmp_path / "eth.json", {"decision": "BLOCK",
        "blocking_reasons": ["ETH_COSTS"]})
    output = tmp_path / "selector.json"
    result = finalize(btc_preflight_path=btc, eth_preflight_path=eth,
        design_path=tmp_path / "missing-design", semantics_path=tmp_path / "missing-semantics",
        runtime_root=tmp_path / "missing-runtime", output_path=output)
    assert result["decision"] == "WAITING_FOR_BOTH_MARKET_PREFLIGHTS"
    assert result["market_data_accessed"] is False
    assert result["performance_accessed"] is False
    assert not output.exists()


def _costs():
    zero = {f"{scenario}_annual_cost_pct": 0 for scenario in
            ("base", "conservative", "stress")}
    return {"by_notional": {"200": {f"{scenario}_roundtrip_bps": 10
            for scenario in ("base", "conservative", "stress")}},
            "carry": {"long": zero, "short": zero}}


def test_replay_requires_byte_equivalent_compact_metrics():
    bars = _bars([(100 + 2 * index, 102 + 2 * index,
                   99 + 2 * index, 101 + 2 * index)
                  for index in range(140)])
    params = _channel_params()
    result = evaluate_point(bars, "channel_breakout", "long", params, _costs())
    row = _compact(1, params, result)
    assert row["decision"] == "PASS_POINT"
    region = {"hypothesis_id": "h", "market": "BTCUSD",
              "mechanism": "channel_breakout", "direction": "long",
              "member_attempts": [1]}
    verified, count = replay_regions([region], {"h": [row]},
                                     {"BTCUSD": bars}, {"BTCUSD": _costs()})
    assert verified == [region] and count == 1
    row["scenarios"]["stress"]["net_pnl_usdc"] += 1
    with pytest.raises(ValueError, match="replay differs"):
        replay_regions([region], {"h": [row]},
                       {"BTCUSD": bars}, {"BTCUSD": _costs()})
