import json
import zipfile
from pathlib import Path

import pytest

from lab.sq_bridge.robustness_trace_v4 import derive, rebuild_from_trace
from lab.sq_bridge.robustness_artifact_v4 import build_artifact
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact
from lab.sq_bridge.sq_temporal_trace_v4 import derive as derive_temporal
from lab.sq_bridge.sqcli_supervised_mc_exports import export_all
from lab.sq_bridge.sqx_monte_carlo_materialize import materialize
from lab.sq_bridge.test_sq_temporal_trace_v4 import _retest_receipt
from lab.sq_bridge.test_sqx_extract import SETTINGS, STRATEGY
from lab.sq_bridge.test_sqx_monte_carlo_contract import _sqx


HEADER = ('"Ticket";"Type";"Open time";"Open price";"Close time";'
          '"Close price";"Size";"Profit/Loss";"MAE ($)"\n')


def _sources(tmp_path):
    orders = tmp_path / "base-orders.csv"
    rows = [HEADER.rstrip()]
    for index in range(30):
        close = "1.0100" if index < 18 else "0.9950"
        pnl = "1" if index < 18 else "-0.5"
        rows.append(
            f'"{index + 1}";"Buy";"2020.01.{index + 1:02d} 00:00:00";"1";'
            f'"2020.01.{index + 1:02d} 12:00:00";"{close}";"100";"{pnl}";"-2"')
    orders.write_text("\n".join(rows) + "\n")
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({
        "contract_type": "observation_position_temporal_split_v4",
        "segments": {
            "train": {"from": "2020-01-01", "to": "2020-12-31"},
            "validation": {"from": "2021-01-02", "to": "2021-12-31"},
            "oos": {"from": "2022-01-02", "to": "2022-12-31"},
            "final_holdout": {"from": "2023-01-02", "to": "2023-12-31"},
        }}, sort_keys=True))
    costs = tmp_path / "costs.json"
    carry = {f"{name}_annual_cost_pct": 0
             for name in ("base", "conservative", "stress")}
    costs.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {"base_roundtrip_bps": 0,
                                    "conservative_roundtrip_bps": 0,
                                    "stress_roundtrip_bps": 0}},
        "carry": {"long": carry, "short": carry}}, sort_keys=True) + "\n")
    receipt = _retest_receipt(tmp_path, orders, candidate_id="T")
    temporal = derive_temporal(
        candidate_id="T", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC", retest_receipt_path=receipt)
    temporal_path = tmp_path / "temporal.json"
    temporal_path.write_text(json.dumps(temporal, indent=2, sort_keys=True) + "\n")

    native = _sqx(tmp_path, count=1000, symbol="NVDA", timeframe="M15")
    with zipfile.ZipFile(native, "a") as archive:
        archive.writestr("settings.xml", SETTINGS)
        archive.writestr("strategy_Portfolio.xml", STRATEGY)
        archive.writestr("version.txt", "3")
    materialized = tmp_path / "project" / "materialized"
    materialize(native, materialized, simulations=1000,
                probability_pct=10, max_change_pct=10)

    exports = tmp_path / "project" / "exports"
    def exporter(command):
        output = command.split(" output=", 1)[1].split(" usecomma", 1)[0]
        relative = output.removeprefix("/sq-projects/")
        target = tmp_path / f"{relative}.csv"
        target.write_text(
            HEADER + ('"1";"Buy";"2020.01.01 00:00:00";"1";'
                      '"2020.01.02 00:00:00";"1.01";"100";"1";"-2"\n'))
        return "ok"
    export_all(
        materialization_manifest=materialized / "materialization.manifest.json",
        output_dir=exports, host_projects_root=tmp_path,
        container_projects_root="/sq-projects", export_fn=exporter)
    return temporal_path, exports / "supervised-mc-exports.receipt.json", costs


def test_builds_and_rebuilds_1000_run_native_source_bound_trace(tmp_path):
    temporal, exports, costs = _sources(tmp_path)
    trace = derive(
        candidate_id="T", temporal_trace_path=temporal,
        mc_export_receipt_path=exports, cost_model_path=costs,
        tested_leverage=5, venue_max_leverage=100,
        allow_synthetic_control=True)
    assert len(trace["monte_carlo_runs"]) == 1000
    assert len(trace["parameter_variants"]) == 1000
    assert len(trace["stress_trades"]) == 30
    assert trace["monte_carlo_runs"][0]["maximum_adverse_excursion_pct"] == 2
    assert rebuild_from_trace(trace) == trace
    trace_path = tmp_path / "robustness.trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    artifact_path = tmp_path / "robustness.artifact.json"
    methodology_path = Path(__file__).with_name("methodology_v4.json")
    artifact = build_artifact(
        campaign_id="campaign", trace_paths=[trace_path],
        cost_model_path=costs, methodology_path=methodology_path,
        artifact_path=artifact_path)
    assert artifact["decision"] == "PASS"
    receipt = {"decision": "PASS", "candidate_ids": ["T"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "robustness", artifact, receipt,
        json.loads(methodology_path.read_text()),
        "campaign", "alquimia_native") == []


def test_rebuild_detects_native_export_tampering(tmp_path):
    temporal, exports, costs = _sources(tmp_path)
    trace = derive(
        candidate_id="T", temporal_trace_path=temporal,
        mc_export_receipt_path=exports, cost_model_path=costs,
        tested_leverage=5, venue_max_leverage=100,
        allow_synthetic_control=True)
    receipt = json.loads(exports.read_text())
    with open(receipt["runs"][0]["orders_csv_path"], "a") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="LINEAGE|manipulada"):
        rebuild_from_trace(trace)
