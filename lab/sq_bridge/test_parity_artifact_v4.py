import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.sq_bridge.parity_artifact_v4 import build_artifact, compare_traces
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _trace(source, *, signals=30, trades=30):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = [(start + timedelta(days=index)).isoformat() for index in range(60)]
    return {
        "schema_version": 1, "trace_type": "strategy_parity_trace",
        "source": source, "candidate_id": "candidate",
        "candles": candles,
        "signals": [{"timestamp": candles[index],
                     "direction": "long" if index % 2 == 0 else "short"}
                    for index in range(signals)],
        "trades": [{"entry_timestamp": candles[index],
                    "exit_timestamp": candles[index + 1],
                    "direction": "long" if index % 2 == 0 else "short",
                    "pnl": float((index % 7) - 3)}
                   for index in range(trades)],
    }


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _build(tmp_path, sq=None, python=None):
    sq_path, py_path = tmp_path / "sq.trace.json", tmp_path / "python.trace.json"
    orders, signals, market, ir = (tmp_path / name for name in (
        "orders.csv", "signals.csv", "market.csv", "candidate.ir.json"))
    for path, value in ((orders, "orders"), (signals, "signals"),
                        (market, "market"), (ir, "ir")):
        path.write_text(value + "\n")
    sq_value, py_value = sq or _trace("strategyquant"), python or _trace("python")
    sq_value.update({
        "orders_path": orders.name,
        "orders_sha256": hashlib.sha256(orders.read_bytes()).hexdigest(),
        "signals_path": signals.name,
        "signals_sha256": hashlib.sha256(signals.read_bytes()).hexdigest(),
        "market_data_path": market.name,
        "market_data_sha256": hashlib.sha256(market.read_bytes()).hexdigest(),
        "source_timezone": "UTC",
        "pnl_semantics": "recomputed_from_prices_at_fixed_notional_before_costs",
    })
    py_value.update({
        "canonical_ir_path": ir.name,
        "canonical_ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest(),
        "market_data_path": market.name,
        "market_data_sha256": hashlib.sha256(market.read_bytes()).hexdigest(),
    })
    _write(sq_path, sq_value)
    _write(py_path, py_value)
    artifact_path = tmp_path / "artifact.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate",
        sq_trace_path=sq_path, python_trace_path=py_path,
        methodology_path=ROOT / "methodology_v4.json",
        report_path=tmp_path / "report.json", artifact_path=artifact_path)
    return artifact, artifact_path


def test_identical_nontrivial_traces_pass_and_validate_from_sources(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    assert artifact["decision"] == "PASS"
    assert artifact["matched_signal_count"] == 30
    assert artifact["matched_trade_count"] == 30
    assert artifact["signal_match_rate"] == artifact["trade_match_rate"] == 1.0
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "parity_pass": True,
               "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "parity", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_zero_or_tiny_samples_cannot_claim_perfect_parity(tmp_path):
    metrics = compare_traces(_trace("strategyquant", signals=0, trades=0),
                             _trace("python", signals=0, trades=0))
    assert metrics["signal_match_rate"] == 0
    assert metrics["trade_match_rate"] == 0
    artifact, _ = _build(
        tmp_path, _trace("strategyquant", signals=1, trades=1),
        _trace("python", signals=1, trades=1))
    assert artifact["decision"] == "REJECT"
    assert artifact["parity_pass"] is False


def test_one_extra_python_signal_rejects_exact_match_gate(tmp_path):
    python = _trace("python", signals=30)
    python["signals"].append({"timestamp": python["candles"][40], "direction": "long"})
    python["signals"].sort(key=lambda row: (row["timestamp"], row["direction"]))
    artifact, _ = _build(tmp_path, python=python)
    assert artifact["decision"] == "REJECT"
    assert artifact["signal_match_rate"] < 1


def test_scaled_pnl_rejects_even_with_perfect_correlation(tmp_path):
    python = _trace("python")
    for trade in python["trades"]:
        trade["pnl"] *= 2
    artifact, _ = _build(tmp_path, python=python)
    assert artifact["pnl_correlation"] == 1.0
    assert artifact["pnl_max_absolute_error_usdc"] > .01
    assert artifact["decision"] == "REJECT"


def test_naive_timestamps_are_rejected_as_ambiguous(tmp_path):
    sq = _trace("strategyquant")
    sq["candles"][0] = "2024-01-01T00:00:00"
    with pytest.raises(ValueError, match="sense zona UTC"):
        _build(tmp_path, sq=sq)


def test_hashed_but_forged_report_is_recomputed_and_rejected(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    report_path = tmp_path / "report.json"
    report = json.loads(report_path.read_text())
    report["matched_trade_count"] = 999
    _write(report_path, report)
    artifact["matched_trade_count"] = 999
    artifact["parity_report_sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "parity_pass": True,
               "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "parity", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:parity:TRACE_CONTRACT" in errors


def test_trace_source_changed_after_capture_invalidates_parity(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    (tmp_path / "signals.csv").write_text("tampered\n")
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "parity_pass": True,
               "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "parity", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:parity:TRACE_CONTRACT" in errors
