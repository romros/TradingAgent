import json
import hashlib
import shutil
import zipfile

import pytest

from lab.sq_bridge.sq_temporal_trace_v4 import derive, rebuild_from_trace
from lab.sq_bridge.sqx_extract import extract
from lab.sq_bridge.test_alquimia_retest import _generate


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _retest_receipt(tmp_path, orders, candidate_id="T"):
    root = tmp_path / f"retest-{candidate_id}"
    root.mkdir()
    manifest, cfx = _generate(root, fixture_candidate_id=candidate_id)
    manifest_path = cfx.with_suffix(".manifest.json")
    imported = root / "imported.cfx"
    shutil.copyfile(cfx, imported)
    candidate = root / "candidate.sqx"
    output = root / "candidate-retested.sqx"
    with zipfile.ZipFile(candidate) as source, zipfile.ZipFile(output, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("orders.bin", b"native-orders")
    log = root / "final.log"
    log.write_text("""TASK FINISHED
Databanks before start: Results (1), PreHoldout (0)
Databanks after finish: Results (1), PreHoldout (1)
Total tested: 1, Passed: 1, Failed: 0
""")
    output_contract = extract(output)
    sync = root / "sync.json"
    sync.write_text(json.dumps({
        "decision": "PASS_RETEST_DATABANK_SYNC", "project_name": "RETEST_T",
        "databank": "Results", "observed_project_strategies": 1,
        "input_copy_sha256": _sha(candidate),
    }))
    output_sync = root / "output-sync.json"
    output_sync.write_text(json.dumps({
        "decision": "PASS_RETEST_OUTPUT_DATABANK_SYNC",
        "project_name": "RETEST_T", "databank": "PreHoldout",
        "observed_output_sqx_count": 1, "output_sqx_sha256": _sha(output),
    }))
    receipt = root / "receipt.json"
    receipt.write_text(json.dumps({
        "decision": "PASS_SUPERVISED_RETEST", "project_name": "RETEST_T",
        "candidate_id": candidate_id, "holdout_accessed": False,
        "performance_filters_applied_in_sq": False,
        "input_before": 1, "output_before": 0, "input_after": 1,
        "output_after": 1, "total_tested": 1, "passed": 1, "failed": 0,
        "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
        "source_cfx_path": str(cfx), "source_cfx_sha256": _sha(cfx),
        "candidate_input_sqx_path": str(candidate),
        "candidate_input_sqx_sha256": _sha(candidate),
        "imported_cfx_path": str(imported), "imported_cfx_sha256": _sha(imported),
        "retest_output_sqx_path": str(output), "retest_output_sqx_sha256": _sha(output),
        "retest_output_strategy_xml_sha256": output_contract["strategy_xml_sha256"],
        "orders_export_input_sqx_path": str(output),
        "orders_export_input_sqx_sha256": _sha(output),
        "orders_csv_path": str(orders), "orders_csv_sha256": _sha(orders),
        "sq_final_log_path": str(log), "sq_final_log_sha256": _sha(log),
        "databank_sync_receipt_path": str(sync),
        "databank_sync_receipt_sha256": _sha(sync),
        "output_databank_sync_receipt_path": str(output_sync),
        "output_databank_sync_receipt_sha256": _sha(output_sync),
    }))
    return receipt


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
    return orders, contract, costs, _retest_receipt(tmp_path, orders)


def test_derives_train_and_annual_oos_windows_from_observed_sq_orders(tmp_path):
    orders, contract, costs, receipt = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1.0000";"2020.01.03 10:00:00";"1.0100"',
        '"2";"Sell";"2021.02.01 10:00:00";"1.0000";"2021.02.02 10:00:00";"0.9900"',
        '"3";"Buy";"2022.03.01 10:00:00";"1.0000";"2022.03.03 10:00:00";"1.0200"',
    ])
    trace = derive(
        candidate_id="T", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC", retest_receipt_path=receipt)
    assert len(trace["train_trades"]) == 1
    assert [row["window_id"] for row in trace["oos_windows"]] == [
        "w001-validation-2021", "w002-oos-2022"]
    assert trace["oos_windows"][0]["trades"][0]["gross_return_pct"] == pytest.approx(1)
    assert trace["oos_windows"][1]["trades"][0]["holding_days"] == 2
    assert rebuild_from_trace(trace) == trace


def test_rebuild_detects_trace_or_source_tampering(tmp_path):
    orders, contract, costs, receipt = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1";"2020.01.03 10:00:00";"1.01"',
    ])
    trace = derive(candidate_id="T", orders_path=orders,
                   temporal_contract_path=contract, cost_model_path=costs,
                   source_timezone="UTC", retest_receipt_path=receipt)
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
    orders, contract, costs, receipt = _sources(tmp_path, [row])
    with pytest.raises(ValueError, match=message):
        derive(candidate_id="T", orders_path=orders,
               temporal_contract_path=contract, cost_model_path=costs,
               source_timezone="UTC", retest_receipt_path=receipt)


def test_rejects_ambiguous_dst_timestamp(tmp_path):
    orders, contract, costs, receipt = _sources(tmp_path, [
        '"1";"Buy";"2021.11.07 01:30:00";"1";"2021.11.08 10:00:00";"1.01"',
    ])
    with pytest.raises(ValueError, match="ambigu"):
        derive(candidate_id="T", orders_path=orders,
               temporal_contract_path=contract, cost_model_path=costs,
               source_timezone="America/New_York", retest_receipt_path=receipt)
