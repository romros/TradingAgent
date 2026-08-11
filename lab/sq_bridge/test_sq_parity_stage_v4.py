import hashlib
import json
from pathlib import Path

import pytest

from lab.sq_bridge.sq_parity_stage_v4 import run_stage
from lab.sq_bridge.sqx_to_ir import canonical_ir, validate_executable_ir


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract(source_hash: str, logic_hash: str = "logic") -> dict:
    action = {
        "op": "EnterAtMarket",
        "params": {
            "#Direction#": 1, "#AllowDuplicateTrades#": False,
            "#ExitAfterBars.ExitAfterBars#": 2,
            "#StopLoss.StopLoss#": {
                "formula": "SQ.Formulas.SLPT.PctValue",
                "params": {"#Value#": 2}},
            "#ProfitTarget.ProfitTarget#": {
                "formula": "SQ.Formulas.SLPT.None", "params": {}},
        },
    }
    return {
        "translation_status": "SUPPORTED_SUBSET", "strategy_name": "T",
        "source_sha256": source_hash, "strategy_xml_sha256": logic_hash,
        "market": {"symbol": "EURUSD", "timeframe": "D1"},
        "execution": {
            "exit_at_end_of_day": False, "exit_on_friday": False,
            "spread_in_sq": 0.0, "slippage_in_sq": 0.0,
            "commission_enabled": False, "swap_enabled": False,
            "dont_trade_on_weekends": True,
            "weekend_friday_close_hhmm": 1700,
            "weekend_sunday_open_hhmm": 1700,
        },
        "entries": {
            "long": {"signal": {"op": "Close", "params": {"#Shift#": 1}},
                     "action": action, "condition_count": 1,
                     "signal_variable_id": "L", "signal_variable_ids_used": ["L"],
                     "entry_gate": {"op": "var", "id": "L"}},
            "short": None,
        },
        "entry_condition_counts": {"long": 1, "short": 0},
        "maximum_entry_conditions": 1, "exit_signals": {},
    }


def _inputs(tmp_path: Path):
    translated_sqx = tmp_path / "translated.sqx"; translated_sqx.write_bytes(b"translated")
    retested_sqx = tmp_path / "retested.sqx"; retested_sqx.write_bytes(b"retested")
    raw = tmp_path / "raw.log"; raw.write_text("1;L;1\n")
    build = tmp_path / "build.json"; build.write_text("{}")
    orders = tmp_path / "orders.csv"; orders.write_text("orders\n")
    market = tmp_path / "market.csv"; market.write_text("market\n")
    ir = canonical_ir(_contract(_sha(translated_sqx)))
    ir_path = tmp_path / "candidate.ir.json"
    ir_path.write_text(json.dumps(ir, sort_keys=True))
    translation_path = tmp_path / "08_python_translation.json"
    translation_path.write_text(json.dumps({
        "stage": "python_translation", "decision": "PASS",
        "campaign_id": "campaign", "candidate_ids": ["T"],
        "translation_exact": True, "evidence_class": "observed",
        "holdout_accessed": False,
        "sqx_path": str(translated_sqx), "sqx_sha256": _sha(translated_sqx),
        "canonical_ir_path": str(ir_path), "canonical_ir_sha256": _sha(ir_path),
        "execution_contract": validate_executable_ir(ir),
    }))
    retest_path = tmp_path / "retest.json"
    retest = {
        "signal_probe_enabled": True,
        "signal_probe_runtime": {
            "decision": "PASS_SIGNAL_PROBE_RUNTIME",
            "build_receipt_path": str(build),
            "build_receipt_sha256": _sha(build)},
        "signal_probe_raw_log_path": str(raw),
        "signal_probe_raw_log_sha256": _sha(raw),
        "retest_output_sqx_path": str(retested_sqx),
        "retest_output_sqx_sha256": _sha(retested_sqx),
        "orders_csv_path": str(orders),
    }
    retest_path.write_text(json.dumps(retest))
    return translation_path, retest_path, market, ir


def _dependencies(tmp_path: Path, ir: dict, *, retest_logic="logic"):
    def verify(path, **_kwargs):
        return json.loads(path.read_text())

    def extract(path):
        if path.name == "retested.sqx":
            return _contract(_sha(path), retest_logic)
        return _contract(_sha(path))

    def normalize(**kwargs):
        kwargs["output_path"].parent.mkdir(parents=True, exist_ok=True)
        kwargs["output_path"].write_bytes(b"normalized")
        value = {"decision": "PASS_VENUE_NEUTRAL_SQX",
                 "strategy_xml_sha256": "logic"}
        kwargs["receipt_path"].write_text(json.dumps(value))
        return value

    def convert(**kwargs):
        kwargs["signals_path"].write_text(
            "Timestamp;Direction\n2024-01-01T00:00:00Z;long\n")
        kwargs["scoped_market_path"].write_text("market\n")
        value = {"decision": "PASS_COMPLETE_SQ_SIGNAL_LOG",
                 "true_entry_signals": 1,
                 "first_logged_bar": "2024-01-01T00:00:00Z",
                 "last_logged_bar": "2024-02-01T00:00:00Z"}
        kwargs["receipt_path"].write_text(json.dumps(value))
        return value

    def sq_trace(**kwargs):
        kwargs["output_path"].write_text(json.dumps({"source": "strategyquant"}))
        return {}

    def py_trace(_ir, _market, _notional, output, _start, _end):
        output.write_text(json.dumps({"source": "python"}))
        return {}

    def parity(**kwargs):
        kwargs["report_path"].write_text(json.dumps({"schema_version": 2}))
        value = {
            "schema_version": 1, "stage": "parity", "campaign_id": "campaign",
            "decision": "PASS", "candidate_ids": ["T"], "holdout_accessed": False,
            "evidence_class": "observed", "parity_pass": True,
            "matched_signal_count": 30, "matched_trade_count": 30,
            "signal_match_rate": 1.0, "trade_match_rate": 1.0,
            "candle_coverage_pct": 100.0, "pnl_correlation": 1.0,
        }
        kwargs["artifact_path"].write_text(json.dumps(value))
        return value

    return dict(retest_verify_fn=verify, normalize_fn=normalize,
                extract_fn=extract, signal_convert_fn=convert,
                sq_trace_fn=sq_trace, python_trace_fn=py_trace,
                parity_fn=parity)


def test_stage_rebuilds_all_sources_and_records_probe_lineage(tmp_path):
    translation, retest, market, ir = _inputs(tmp_path)
    artifact_path = tmp_path / "09_parity.json"
    result = run_stage(
        campaign_id="campaign", translation_artifact_path=translation,
        retest_receipt_path=retest, market_data_path=market,
        methodology_path=tmp_path / "methodology.json",
        work_dir=tmp_path / "parity-work", artifact_path=artifact_path,
        **_dependencies(tmp_path, ir))
    assert result["decision"] == "PASS"
    assert result["probe_bound_supervised_retest"] is True
    assert result["notional_usdc"] == 200
    bundle = Path(result["parity_source_bundle_path"])
    bundle = artifact_path.parent / bundle
    assert json.loads(bundle.read_text())["decision"] == "PASS_PARITY_SOURCE_BUNDLE"


def test_stage_rejects_retest_with_different_strategy_logic(tmp_path):
    translation, retest, market, ir = _inputs(tmp_path)
    with pytest.raises(ValueError, match="LOGIC_DIFFERS"):
        run_stage(
            campaign_id="campaign", translation_artifact_path=translation,
            retest_receipt_path=retest, market_data_path=market,
            methodology_path=tmp_path / "methodology.json",
            work_dir=tmp_path / "parity-work", artifact_path=tmp_path / "out.json",
            **_dependencies(tmp_path, ir, retest_logic="different"))
