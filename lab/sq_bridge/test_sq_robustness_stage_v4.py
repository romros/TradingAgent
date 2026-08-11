import json
from pathlib import Path

import pytest

from lab.sq_bridge.sq_robustness_stage_v4 import run_stage
from lab.sq_bridge.sq_temporal_trace_v4 import derive as derive_temporal
from lab.sq_bridge.test_sq_temporal_trace_v4 import _sources


def _sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path):
    orders, contract, _, receipt = _sources(tmp_path, [
        '"1";"Buy";"2020.01.02 10:00:00";"1";"2020.01.03 10:00:00";"1.01";"100";"-2"',
    ])
    carry = {f"{name}_annual_cost_pct": 0
             for name in ("base", "conservative", "stress")}
    costs = tmp_path / "costs-frozen.json"
    costs.write_text(json.dumps({
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "by_notional": {"200": {"base_roundtrip_bps": 0,
                                    "conservative_roundtrip_bps": 0,
                                    "stress_roundtrip_bps": 0}},
        "carry": {"long": carry, "short": carry}}))
    trace = derive_temporal(
        candidate_id="T", orders_path=orders,
        temporal_contract_path=contract, cost_model_path=costs,
        source_timezone="UTC", retest_receipt_path=receipt)
    trace_path = tmp_path / "T.temporal.trace.json"
    trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")
    temporal = tmp_path / "04_temporal_validation.json"
    temporal.write_text(json.dumps({
        "stage": "temporal_validation", "decision": "PASS",
        "campaign_id": "campaign", "holdout_accessed": False,
        "candidate_ids": ["T"], "candidate_temporal_metrics": {"T": {}},
        "supervised_retest_evidence": {"T": {
            "supervised_retest_receipt_path": str(receipt),
            "supervised_retest_receipt_sha256": _sha(receipt),
            "temporal_trace_path": str(trace_path),
            "temporal_trace_sha256": _sha(trace_path),
        }}}))
    return temporal, costs


def _mocks(calls):
    def generate_mc(**kwargs):
        calls["generate"] += 1
        kwargs["output"].write_bytes(b"mc-cfx")
        kwargs["output"].with_suffix(".manifest.json").write_text(
            json.dumps({"candidate_id": "T"}))

    def verify_mc(_cfx, manifest):
        return {"candidate_id": manifest["candidate_id"]}

    def mc(**kwargs):
        calls["mc"] += 1
        output = kwargs["output_dir"]
        output.mkdir(parents=True, exist_ok=True)
        native = output / "native.sqx"
        native.write_bytes(b"native")
        receipt = {"decision": "PASS_SUPERVISED_MONTE_CARLO",
                   "candidate_id": "T", "retest_output_sqx_path": str(native)}
        (output / "supervised_monte_carlo_receipt.json").write_text(json.dumps(receipt))
        return receipt

    def materialize(_source, output, **_kwargs):
        calls["materialize"] += 1
        output.mkdir(parents=True, exist_ok=True)
        result = {"evidence_class": "observed"}
        (output / "materialization.manifest.json").write_text(json.dumps(result))
        return result

    def export(**kwargs):
        calls["export"] += 1
        output = kwargs["output_dir"]
        output.mkdir(parents=True, exist_ok=True)
        result = {"decision": "PASS_SUPERVISED_MC_EXPORTS", "completed_count": 1000}
        (output / "supervised-mc-exports.receipt.json").write_text(json.dumps(result))
        return result

    def derive(**kwargs):
        calls["derive"].append(kwargs["tested_leverage"])
        return {"candidate_id": "T", "tested_leverage": kwargs["tested_leverage"]}

    def evaluate(trace, *_args):
        leverage = trace["tested_leverage"]
        return {"monte_carlo_runs": 1000, "profitable_monte_carlo_ratio": .8,
                "parameter_variant_count": 1000,
                "profitable_parameter_variants_ratio": .8,
                "stress_profit_factor": 1.2,
                "liquidation_probability": 0 if leverage <= 10 else .01,
                "tested_leverage": leverage}

    def artifact(**kwargs):
        calls["artifact"] += 1
        trace = json.loads(kwargs["trace_paths"][0].read_text())
        result = {"stage": "robustness", "campaign_id": "campaign",
                  "decision": "PASS", "candidate_ids": ["T"],
                  "holdout_accessed": False,
                  "maximum_tested_leverage": trace["tested_leverage"]}
        kwargs["artifact_path"].write_text(json.dumps(result))
        return result
    return generate_mc, verify_mc, mc, materialize, export, derive, evaluate, artifact


def test_orchestrates_native_robustness_and_selects_highest_safe_leverage(tmp_path):
    temporal, costs = _inputs(tmp_path)
    calls = {"generate": 0, "mc": 0, "materialize": 0, "export": 0,
             "derive": [], "artifact": 0}
    funcs = _mocks(calls)
    root = tmp_path / "projects"
    result = run_stage(
        campaign_id="campaign", temporal_artifact_path=temporal,
        methodology_path=Path(__file__).with_name("methodology_v4.json"),
        cost_model_path=costs, work_dir=root / "robustness",
        host_projects_root=root, artifact_path=tmp_path / "05_robustness.json",
        venue_max_leverage=200, execution_max_leverage=100,
        generate_mc_fn=funcs[0], verify_mc_fn=funcs[1], mc_fn=funcs[2],
        materialize_fn=funcs[3], export_fn=funcs[4], derive_fn=funcs[5],
        evaluate_fn=funcs[6], artifact_fn=funcs[7])
    assert result["maximum_tested_leverage"] == 10
    assert calls["derive"] == [100, 75, 50, 30, 20, 15, 10]
    scan = result["supervised_monte_carlo_evidence"]["T"]["leverage_scan"]
    assert scan[-1]["passes"] is True
    assert calls == {"generate": 1, "mc": 1, "materialize": 1,
                     "export": 1, "derive": [100, 75, 50, 30, 20, 15, 10],
                     "artifact": 1}


def test_frozen_costs_and_mounted_workdir_are_mandatory(tmp_path):
    temporal, costs = _inputs(tmp_path)
    model = json.loads(costs.read_text())
    model["costs_frozen"] = False
    costs.write_text(json.dumps(model))
    with pytest.raises(ValueError, match="FROZEN"):
        run_stage(
            campaign_id="campaign", temporal_artifact_path=temporal,
            methodology_path=Path(__file__).with_name("methodology_v4.json"),
            cost_model_path=costs, work_dir=tmp_path / "work",
            host_projects_root=tmp_path / "projects",
            artifact_path=tmp_path / "artifact.json", venue_max_leverage=100,
            execution_max_leverage=100)
