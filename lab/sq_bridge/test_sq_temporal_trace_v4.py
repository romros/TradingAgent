import json

import pytest

from lab.sq_bridge.sq_temporal_trace_v4 import derive, rebuild_from_trace


def _sources(tmp_path, rows):
    orders = tmp_path / "orders.csv"
    header = '"Ticket";"Type";"Open time";"Open price";"Close time";"Close price"'
    orders.write_text("\n".join([header, *rows]) + "\n")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-02", "to": "2021-12-31"},
            "oos": {"from": "2022-01-02", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-02", "to": "2023-12-31"},
        },
    }, sort_keys=True))
    costs = tmp_path / "costs.json"
    costs.write_text('{"decision":"PASS_COSTS_FROZEN"}\n')
    return orders, contract, costs


def test_derives_train_and_annual_oos_windows_from_observed_sq_orders(tmp_path):
    orders, contract, costs = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1.0000";"2020.01.03 10:00:00";"1.0100"',
        '"2";"Sell";"2021.02.01 10:00:00";"1.0000";"2021.02.02 10:00:00";"0.9900"',
        '"3";"Buy";"2022.03.01 10:00:00";"1.0000";"2022.03.03 10:00:00";"1.0200"',
    ])
    trace = derive(
        candidate_id="candidate", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC")
    assert len(trace["train_trades"]) == 1
    assert [row["window_id"] for row in trace["oos_windows"]] == [
        "w001-validation-2021", "w002-oos-2022"]
    assert trace["oos_windows"][0]["trades"][0]["gross_return_pct"] == pytest.approx(1)
    assert trace["oos_windows"][1]["trades"][0]["holding_days"] == 2
    assert rebuild_from_trace(trace) == trace


def test_rebuild_detects_trace_or_source_tampering(tmp_path):
    orders, contract, costs = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1";"2020.01.03 10:00:00";"1.01"',
    ])
    trace = derive(candidate_id="c", orders_path=orders,
                   temporal_contract_path=contract, cost_model_path=costs,
                   source_timezone="UTC")
    trace["train_trades"][0]["gross_return_pct"] = 99
    assert rebuild_from_trace(trace) != trace
    orders.write_text(orders.read_text().replace("1.01", "1.02"))
    with pytest.raises(ValueError, match="manipulada"):
        rebuild_from_trace(trace)


@pytest.mark.parametrize(("row", "message"), [
    ('"1";"Buy";"2022.12.30 10:00:00";"1";"2023.01.03 10:00:00";"1.01"',
     "holdout"),
    ('"1";"Buy";"2020.12.30 10:00:00";"1";"2021.01.03 10:00:00";"1.01"',
     "frontera"),
])
def test_rejects_holdout_and_cross_segment_trades(tmp_path, row, message):
    orders, contract, costs = _sources(tmp_path, [row])
    with pytest.raises(ValueError, match=message):
        derive(candidate_id="c", orders_path=orders,
               temporal_contract_path=contract, cost_model_path=costs,
               source_timezone="UTC")


def test_rejects_ambiguous_dst_timestamp(tmp_path):
    orders, contract, costs = _sources(tmp_path, [
        '"1";"Buy";"2021.11.07 01:30:00";"1";"2021.11.08 10:00:00";"1.01"',
    ])
    with pytest.raises(ValueError, match="ambigu"):
        derive(candidate_id="c", orders_path=orders,
               temporal_contract_path=contract, cost_model_path=costs,
               source_timezone="America/New_York")
