import hashlib
import json

import pytest

import lab.sq_bridge.final_holdout_trace_v4 as module


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    orders = tmp_path / "orders.csv"
    orders.write_text(
        '"Ticket";"Type";"Open time";"Open price";"Close time";"Close price"\n'
        '"1";"Buy";"2023.02.01 10:00:00";"100";"2023.02.02 10:00:00";"101"\n')
    contract = tmp_path / "split.json"
    contract.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-01", "to": "2021-12-31"},
            "oos": {"from": "2022-01-01", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-01", "to": "2023-12-31"}}}))
    costs = tmp_path / "costs.json"
    costs.write_text('{"decision":"PASS_COSTS_FROZEN"}\n')
    sizing = tmp_path / "small.json"
    sizing.write_text(json.dumps({
        "stage": "small_account_economics", "decision": "PASS",
        "candidate_ids": ["T"], "holdout_accessed": False,
        "position_notional_usdc": 200, "risk_per_trade_pct": 1.5,
        "selected_leverage": 5, "cost_model_sha256": _sha(costs)}))
    receipt = tmp_path / "receipt.json"; receipt.write_text("{}")
    sqx = tmp_path / "output.sqx"; sqx.write_bytes(b"sqx")
    candles = tmp_path / "candles.csv"; candles.write_text("candles")
    candle_contract = tmp_path / "candle-contract.json"; candle_contract.write_text("{}")
    return orders, contract, costs, sizing, receipt, sqx, candles, candle_contract


def test_derives_single_source_bound_dynamic_holdout_trace(tmp_path, monkeypatch):
    orders, contract, costs, sizing, receipt, sqx, candles, candle_contract = _inputs(tmp_path)
    monkeypatch.setattr(module, "verify_supervised_retest_receipt",
                        lambda *args, **kwargs: {"retest_output_sqx_path": str(sqx)})

    def reconstruct(**kwargs):
        trade = kwargs["source_trades"][0]
        return [{**{key: trade[key] for key in (
            "trade_id", "entry_timestamp", "gross_return_pct", "side", "holding_days")},
            "initial_stop_distance_pct": 2}], {
            "source_sqx_path": str(sqx.resolve()), "source_sqx_sha256": _sha(sqx),
            "source_strategy_xml_sha256": "strategy",
            "candles_path": str(candles.resolve()), "candles_sha256": _sha(candles),
            "candle_contract_path": str(candle_contract.resolve()),
            "candle_contract_sha256": _sha(candle_contract),
            "candle_timezone": "UTC",
            "stop_distance_semantics": "SQ_initial_ATR_previous_bar_or_fixed_percent"}
    monkeypatch.setattr(module, "reconstruct", reconstruct)
    trace = module.derive(
        candidate_id="T", orders_path=orders,
        supervised_holdout_receipt_path=receipt,
        temporal_contract_path=contract, small_account_artifact_path=sizing,
        cost_model_path=costs, source_timezone="UTC", candles_path=candles,
        candle_timezone="UTC", candle_contract_path=candle_contract)
    assert trace["schema_version"] == 2
    assert trace["holdout_evaluation_count"] == 1
    assert trace["trades"][0]["gross_return_pct"] == 1
    assert trace["trades"][0]["initial_stop_distance_pct"] == 2
    assert module.rebuild_from_trace(trace) == trace


def test_rejects_any_trade_crossing_the_sealed_holdout_boundary(tmp_path, monkeypatch):
    orders, contract, costs, sizing, receipt, sqx, candles, candle_contract = _inputs(tmp_path)
    orders.write_text(orders.read_text().replace(
        "2023.02.01 10:00:00", "2022.12.31 10:00:00"))
    monkeypatch.setattr(module, "verify_supervised_retest_receipt",
                        lambda *args, **kwargs: {"retest_output_sqx_path": str(sqx)})
    with pytest.raises(ValueError, match="creuant"):
        module.derive(
            candidate_id="T", orders_path=orders,
            supervised_holdout_receipt_path=receipt,
            temporal_contract_path=contract, small_account_artifact_path=sizing,
            cost_model_path=costs, source_timezone="UTC", candles_path=candles,
            candle_timezone="UTC", candle_contract_path=candle_contract)
