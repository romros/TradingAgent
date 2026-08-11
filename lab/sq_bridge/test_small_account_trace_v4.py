import json
from datetime import datetime, timedelta

import pytest

from lab.sq_bridge.small_account_trace_v4 import derive, rebuild_from_trace
from lab.sq_bridge.candle_source_contract_v4 import build as build_candle_contract
from lab.sq_bridge.sq_temporal_trace_v4 import derive as derive_temporal
from lab.sq_bridge.test_sq_temporal_trace_v4 import _retest_receipt


def _inputs(tmp_path):
    orders = tmp_path / "orders.csv"
    orders.write_text(
        '"Ticket";"Type";"Open time";"Open price";"Close time";"Close price";"Size";"MAE ($)"\n'
        '"1";"Buy";"2020.01.02 10:00:00";"100";"2020.01.02 11:00:00";"101";"1";"-2"\n')
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-02", "to": "2021-12-31"},
            "oos": {"from": "2022-01-02", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-02", "to": "2023-12-31"}}}))
    costs = tmp_path / "costs.json"
    costs.write_text('{"decision":"PASS_COSTS_FROZEN"}\n')
    receipt = _retest_receipt(tmp_path, orders, candidate_id="T")
    temporal = derive_temporal(
        candidate_id="T", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC", retest_receipt_path=receipt)
    temporal_path = tmp_path / "temporal.trace.json"
    temporal_path.write_text(json.dumps(temporal, indent=2, sort_keys=True) + "\n")
    candles = tmp_path / "candles.csv"
    lines = ["Date,Time,Open,High,Low,Close,Volume"]
    start = datetime(2020, 1, 2, 5)
    for index in range(25):
        stamp = start + timedelta(minutes=15 * index)
        lines.append(f"{stamp:%Y.%m.%d},{stamp:%H:%M},100,101,99,100,1")
    candles.write_text("\n".join(lines) + "\n")
    dukascopy = tmp_path / "dukascopy.csv"
    dukascopy.write_bytes(candles.read_bytes())
    candle_contract = tmp_path / "candle-contract.json"
    candle_contract.write_text(json.dumps(build_candle_contract(
        sq_candles_path=candles, sq_timezone="UTC",
        dukascopy_candles_path=dukascopy, dukascopy_timezone="UTC",
        symbol="NVDA", timeframe="M15"), indent=2, sort_keys=True) + "\n")
    return temporal_path, candles, costs, candle_contract


def test_reconstructs_exact_previous_bar_sq_atr_stop(tmp_path):
    temporal, candles, costs, candle_contract = _inputs(tmp_path)
    trace = derive(
        candidate_id="T", temporal_trace_path=temporal,
        candles_path=candles, candle_timezone="UTC",
        candle_contract_path=candle_contract,
        cost_model_path=costs, venue_max_leverage=100)
    assert trace["schema_version"] == 2
    assert trace["trades"][0]["initial_stop_distance_pct"] == 4
    assert trace["stop_distance_semantics"] == "SQ_initial_ATR_previous_bar_or_fixed_percent"
    assert rebuild_from_trace(trace) == trace


def test_rejects_entry_price_or_candle_source_tampering(tmp_path):
    temporal, candles, costs, candle_contract = _inputs(tmp_path)
    trace = derive(candidate_id="T", temporal_trace_path=temporal,
                   candles_path=candles, candle_timezone="UTC",
                   candle_contract_path=candle_contract,
                   cost_model_path=costs, venue_max_leverage=100)
    candles.write_text(candles.read_text().replace(",100,101,99,100,1", ",100,102,99,100,1", 1))
    with pytest.raises(ValueError, match="manipulada"):
        rebuild_from_trace(trace)

    value = json.loads(temporal.read_text())
    value["train_trades"][0]["entry_price"] = 99
    temporal.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="reproduible"):
        derive(candidate_id="T", temporal_trace_path=temporal,
               candles_path=candles, candle_timezone="UTC",
               candle_contract_path=candle_contract,
               cost_model_path=costs, venue_max_leverage=100)
