import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lab.sq_bridge.e2e_control import payload
from lab.sq_bridge.paper_package_artifact_v4 import build_artifact
from lab.sq_bridge.paper_order_sizing_v4 import size_entry
from lab.sq_bridge.paper_signal_instruction_v4 import build_instruction
from lab.sq_bridge.paper_quote_probe_v4 import fetch_latest_quote, run_probe
from lab.sq_bridge.ostium_order_payload_v4 import (
    build_order_template, revalidate_fresh_quote,
)
from lab.sq_bridge.stage_artifact_contract import validate_stage_artifact


ROOT = Path(__file__).parent


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _sources(tmp_path):
    candidate = "candidate"
    result = {}
    costs = tmp_path / "costs.json"
    carry = {scenario + "_annual_cost_pct": 0
             for scenario in ("base", "conservative", "stress")}
    _write(costs, {
        "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "entry_debit": {
            "maximum_observed_open_fee_bps": 2,
            "minimum_observed_open_fee_bps": 2,
            "oracle_locked_usdc": .1,
            "collateral_semantics": (
                "gross submitted collateral; Ostium deducts opening fee and "
                "oracle before deriving final notional"),
            "sizing_policy": "never gross up from a stale fee observation",
        },
        "by_notional": {"500": {
            "base_roundtrip_bps": 0,
            "conservative_roundtrip_bps": 1,
            "stress_roundtrip_bps": 2,
        }},
        "carry": {"long": carry, "short": carry},
    })
    for stage, holdout in (("market_preflight", False),
                           ("small_account_economics", False),
                           ("final_holdout_validation", True),
                           ("python_translation", False), ("parity", False)):
        ids = [] if stage == "market_preflight" else [candidate]
        value = payload(stage, ids, holdout)
        value.update({"campaign_id": "campaign", "evidence_class": "observed"})
        value.pop("control_purpose", None)
        path = tmp_path / f"{stage}.json"
        result[stage] = path
        if stage == "python_translation":
            ir = tmp_path / "candidate.ir.json"
            _write(ir, {
                "schema_version": 1, "ir_type": "alquimia_strategy_ir",
                "translation_semantics": "exact_supported_subset",
                "strategy_id": candidate,
                "market": {"symbol": "EURUSD_TEST", "timeframe": "D1"},
                "execution": {
                    "exit_at_end_of_day": False, "exit_on_friday": False,
                    "spread_in_sq": 0, "slippage_in_sq": 0,
                    "commission_enabled": False, "swap_enabled": False,
                    "dont_trade_on_weekends": True,
                    "weekend_friday_close_hhmm": 1700,
                    "weekend_sunday_open_hhmm": 1700,
                },
                "entries": {
                    "long": {"signal": {"op": "IsGreater", "children": [
                        {"op": "Close", "params": {"#Shift#": 1}},
                        {"op": "Number", "params": {"#Value#": 0}},
                    ]}}, "short": None,
                },
                "trade_plans": {
                    "long": {
                        "entry_order": "market_at_signal_bar_open",
                        "allow_duplicate_trades": False, "exit_after_bars": 5,
                        "stop_loss": {"type": "atr", "multiple": .5, "period": 2},
                        "profit_target": {"type": "none"},
                    }, "short": None,
                },
            })
            value.update({"canonical_ir_path": ir.name,
                          "canonical_ir_sha256": hashlib.sha256(ir.read_bytes()).hexdigest()})
        if stage == "parity":
            report = tmp_path / "candidate.parity.json"
            _write(report, {"candidate_id": candidate})
            value.update({"parity_report_path": report.name,
                          "parity_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest()})
        if stage == "small_account_economics":
            value.update({
                "minimum_position_notional_usdc": 150,
                "maximum_position_notional_usdc": value["position_notional_usdc"],
                "venue_minimum_notional_usdc": 5,
                "maximum_holding_days": 5,
                "maximum_portfolio_margin_pct_policy": 35,
                "minimum_reserve_pct_policy": 40,
                "minimum_stop_to_liquidation_buffer_ratio_policy": 1.5,
                "cost_model_path": costs.name,
                "cost_model_sha256": hashlib.sha256(costs.read_bytes()).hexdigest(),
            })
        _write(path, value)
    return result


def _build(tmp_path):
    paths = _sources(tmp_path)
    artifact_path = tmp_path / "paper-stage.json"
    artifact = build_artifact(
        campaign_id="campaign", candidate_id="candidate", source_artifact_paths=paths,
        config_path=tmp_path / "paper.json", artifact_path=artifact_path)
    return artifact, artifact_path


def test_paper_package_binds_ostium_risk_ir_and_parity_without_signer(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    config = json.loads((tmp_path / "paper.json").read_text())
    assert config["ostium_pair_id"] == "control-pair"
    assert config["selected_leverage"] == 5
    assert config["execution_max_leverage"] == 100
    assert config["capital_committed_usdc"] == 60
    assert config["reserve_usdc"] == 140
    assert config["risk_per_trade_pct"] == 1.5
    assert config["risk_per_trade_fraction"] == .015
    assert config["risk_unit"] == "percentage_points_in_risk_per_trade_pct"
    assert config["sizing_policy"] == (
        "risk_budget_over_runtime_initial_stop_capped_by_validated_notional")
    assert config["dynamic_stop_sizing"] is True
    assert config["minimum_position_notional_usdc"] == 150
    assert config["maximum_position_notional_usdc"] == 300
    assert config["venue_minimum_notional_usdc"] == 5
    assert len(config["cost_model_sha256"]) == 64
    assert config["stop_loss_required"] is True
    assert config["liquidation_model"] == "ostium_threshold_cost_buffered"
    assert config["mode"] == "paper"
    assert config["signer_enabled"] is config["live_authorized"] is False
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    assert validate_stage_artifact(
        "paper", artifact, receipt, methodology,
        "campaign", "alquimia_native") == []


def test_config_cannot_raise_leverage_after_validation_even_if_rehashed(tmp_path):
    artifact, artifact_path = _build(tmp_path)
    config_path = tmp_path / "paper.json"
    config = json.loads(config_path.read_text())
    config["selected_leverage"] = 100
    _write(config_path, config)
    artifact["paper_config_sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    methodology = json.loads((ROOT / "methodology_v4.json").read_text())
    receipt = {"decision": "PASS", "candidate_ids": ["candidate"],
               "holdout_accessed": False, "artifact": str(artifact_path)}
    errors = validate_stage_artifact(
        "paper", artifact, receipt, methodology,
        "campaign", "alquimia_native")
    assert "STAGE_ARTIFACT:paper:PACKAGE_CONTRACT" in errors


def test_package_rejects_source_artifact_from_another_candidate(tmp_path):
    paths = _sources(tmp_path)
    parity = json.loads(paths["parity"].read_text())
    parity["candidate_ids"] = ["other"]
    _write(paths["parity"], parity)
    with pytest.raises(ValueError, match="lineage mismatch"):
        build_artifact(
            campaign_id="campaign", candidate_id="candidate", source_artifact_paths=paths,
            config_path=tmp_path / "paper.json", artifact_path=tmp_path / "stage.json")


def test_verified_package_sizes_dynamic_stop_without_sending_order(tmp_path):
    _build(tmp_path)
    result = size_entry(
        config_path=tmp_path / "paper.json", equity_usdc=200,
        initial_stop_distance_pct=1, side="long", maximum_holding_days=5)
    assert result["decision"] == "PASS_PAPER_ENTRY_SIZING"
    assert result["order_sent"] is False
    assert result["risk_budget_usdc"] == pytest.approx(3)
    assert result["actual_stop_risk_usdc"] == pytest.approx(3)
    assert result["position_notional_usdc"] == pytest.approx(300)
    assert result["collateral_usdc"] == pytest.approx(60)
    assert result["execution_max_leverage"] == 100
    assert result["stress_entry_cost_usdc"] == pytest.approx(.06)


def test_runtime_sizing_caps_tight_stop_and_rejects_unvalidated_wide_stop(tmp_path):
    _build(tmp_path)
    tight = size_entry(
        config_path=tmp_path / "paper.json", equity_usdc=200,
        initial_stop_distance_pct=.5, side="short", maximum_holding_days=5)
    assert tight["uncapped_position_notional_usdc"] == pytest.approx(600)
    assert tight["position_notional_usdc"] == pytest.approx(300)
    assert tight["notional_capped"] is True
    assert tight["actual_stop_risk_usdc"] == pytest.approx(1.5)
    with pytest.raises(ValueError, match="envolupant validada"):
        size_entry(
            config_path=tmp_path / "paper.json", equity_usdc=200,
            initial_stop_distance_pct=3, side="long", maximum_holding_days=5)


def test_ir_signal_builds_atr_sized_inert_paper_instruction(tmp_path):
    import pandas as pd

    _build(tmp_path)
    index = pd.date_range("2026-08-03", periods=4, freq="B", tz="UTC")
    frame = pd.DataFrame({
        "open": [100, 101, 102, 103], "high": [102, 103, 104, 105],
        "low": [99, 100, 101, 102], "close": [101, 102, 103, 104],
    }, index=index)
    result = build_instruction(
        config_path=tmp_path / "paper.json", frame=frame, equity_usdc=200)
    assert result["decision"] == "PASS_PAPER_SIGNAL_INSTRUCTION"
    assert result["order_sent"] is False
    assert result["side"] == "long"
    # Previous-bar SQ ATR(2) is 3, rounded before applying the 2x multiple.
    assert result["initial_stop_distance_pct"] == pytest.approx(1.5 / 103 * 100)
    assert result["stop_price"] == pytest.approx(101.5)
    assert result["maximum_holding_days_for_cost_buffer"] == 14


def _signal(tmp_path):
    import pandas as pd

    _build(tmp_path)
    index = pd.date_range("2026-08-03", periods=4, freq="B", tz="UTC")
    frame = pd.DataFrame({
        "open": [100, 101, 102, 103], "high": [102, 103, 104, 105],
        "low": [99, 100, 101, 102], "close": [101, 102, 103, 104],
    }, index=index)
    return build_instruction(
        config_path=tmp_path / "paper.json", frame=frame, equity_usdc=200)


def _registry(tmp_path):
    path = tmp_path / "markets.json"
    _write(path, {"markets": {"CONTROL": {
        "ostium_pair": "control-pair", "bs_symbol": "EURUSD"}}})
    return path


def test_signal_maps_to_exact_inert_brokerage_request(tmp_path):
    signal = _signal(tmp_path)
    result = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=_registry(tmp_path))
    body = result["request_body"]
    assert result["decision"] == "PREPARED_INERT_ORDER_TEMPLATE"
    assert result["endpoint"] == "/api/v1/broker/orders/open"
    async_contract = result["brokerage_async_contract"]
    assert async_contract["initial_http_status"] == 202
    assert async_contract["initial_response_semantics"] == "pending_ack_not_fill"
    assert async_contract["operation_id_required"] is True
    assert async_contract["operation_poll_endpoint_template"] == (
        "/api/v1/broker/operations/{operation_id}")
    assert async_contract["terminal_states"] == ["confirmed", "error"]
    assert async_contract["post_open_position_reconciliation_required"] is True
    assert async_contract["effective_notional_must_be_measured_from_confirmed_position"] is True
    assert body["venue"] == "ostium"
    assert body["symbol"] == "EURUSD"
    assert body["side"] == "long"
    assert body["collateral"] * body["leverage"] == pytest.approx(
        signal["position_notional_usdc"])
    assert result["entry_notional_semantics"] == (
        "target_is_zero_fee_upper_bound_not_guaranteed_fill")
    envelope = result["entry_notional_envelope"]
    target = signal["position_notional_usdc"]
    leverage = signal["selected_leverage"]
    opening_fee = target * 2 / 10_000
    effective_collateral = signal["collateral_usdc"] - opening_fee - .1
    effective_notional = effective_collateral * leverage
    assert envelope["gross_notional_upper_bound_usdc"] == pytest.approx(target)
    assert envelope["conservative_opening_fee_usdc"] == pytest.approx(opening_fee)
    assert envelope["oracle_locked_usdc"] == pytest.approx(.1)
    assert envelope["conservative_effective_collateral_usdc"] == pytest.approx(
        effective_collateral)
    assert envelope["conservative_effective_notional_usdc"] == pytest.approx(
        effective_notional)
    assert envelope["underfill_usdc"] == pytest.approx(target - effective_notional)
    assert body["sl_price"] < signal["entry_price"]
    assert body["tp_price"] is None
    assert body["client_order_id"].startswith("alq4-")
    assert result["fresh_quote_required"] is True
    assert result["request_sent"] is result["signer_enabled"] is False
    assert result["live_authorized"] is False


def test_order_mapping_is_idempotent_and_rejects_tampering_or_caps(tmp_path):
    signal = _signal(tmp_path)
    registry = _registry(tmp_path)
    first = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=registry)
    second = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=registry)
    assert first["request_body"]["client_order_id"] == second["request_body"][
        "client_order_id"]

    tampered = dict(signal, candidate_id="other")
    with pytest.raises(ValueError, match="lineage"):
        build_order_template(
            config_path=tmp_path / "paper.json", instruction=tampered,
            operational_max_leverage=10, registry_path=registry)

    over_cap = dict(signal, selected_leverage=101,
                    collateral_usdc=signal["position_notional_usdc"] / 101)
    with pytest.raises(ValueError, match="limit executable"):
        build_order_template(
            config_path=tmp_path / "paper.json", instruction=over_cap,
            operational_max_leverage=200, registry_path=registry)

    with pytest.raises(ValueError, match="limit executable"):
        build_order_template(
            config_path=tmp_path / "paper.json", instruction=signal,
            operational_max_leverage=4, registry_path=registry)


def test_no_signal_never_creates_request_body(tmp_path):
    _build(tmp_path)
    result = build_order_template(
        config_path=tmp_path / "paper.json",
        instruction={"decision": "NO_PAPER_SIGNAL", "order_sent": False,
                     "signal_timestamp": "2026-08-03T00:00:00+00:00"},
        operational_max_leverage=10)
    assert result["decision"] == "NO_ORDER_TEMPLATE"
    assert result["request_sent"] is False
    assert "request_body" not in result


def test_fresh_quote_revalidates_stop_risk_spread_without_sending(tmp_path):
    signal = _signal(tmp_path)
    template = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=_registry(tmp_path))
    now = datetime(2026, 8, 11, 12, 0, 5, tzinfo=timezone.utc)
    result = revalidate_fresh_quote(
        template=template,
        quote={"symbol": "EURUSD", "bid": 102.995, "ask": 103.005,
               "mid": 103, "timestamp": (now - timedelta(seconds=5)).isoformat()},
        observed_at=now)
    assert result["decision"] == "PASS_FRESH_QUOTE_REVALIDATION"
    assert result["paper_request_ready"] is True
    assert result["fresh_quote_required"] is False
    assert result["runtime_stop_risk_usdc"] == pytest.approx(
        signal["risk_budget_usdc"])
    assert result["request_sent"] is result["signer_enabled"] is False
    assert result["live_authorized"] is False


def test_quote_gate_rejects_stale_risky_or_wide_quotes(tmp_path):
    signal = _signal(tmp_path)
    template = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=_registry(tmp_path))
    now = datetime(2026, 8, 11, 12, 0, 30, tzinfo=timezone.utc)
    base = {"symbol": "EURUSD", "bid": 102.995, "ask": 103.005,
            "mid": 103, "timestamp": now.isoformat()}
    with pytest.raises(ValueError, match="caducat"):
        revalidate_fresh_quote(
            template=template,
            quote={**base, "timestamp": (now - timedelta(seconds=11)).isoformat()},
            observed_at=now)
    with pytest.raises(ValueError, match="risc runtime"):
        revalidate_fresh_quote(
            template=template,
            quote={**base, "bid": 103.095, "ask": 103.105, "mid": 103.1},
            observed_at=now)
    with pytest.raises(ValueError, match="spread live"):
        revalidate_fresh_quote(
            template=template,
            quote={**base, "bid": 102.98, "ask": 103.02},
            observed_at=now)


def test_read_only_quote_probe_uses_get_and_persists_inert_receipt(tmp_path):
    signal = _signal(tmp_path)
    template = build_order_template(
        config_path=tmp_path / "paper.json", instruction=signal,
        operational_max_leverage=10, registry_path=_registry(tmp_path))
    template_path = tmp_path / "template.json"
    _write(template_path, template)
    now = datetime(2026, 8, 11, 12, 0, 5, tzinfo=timezone.utc)
    calls = []

    def fetch(**kwargs):
        calls.append(kwargs)
        return {"symbol": "EURUSD", "bid": 102.995, "ask": 103.005,
                "mid": 103, "timestamp": now.isoformat()}

    output = tmp_path / "quote-receipt.json"
    result = run_probe(
        template_path=template_path, output_path=output,
        base_url="http://broker", observed_at=now, fetch_fn=fetch)
    assert calls == [{"base_url": "http://broker", "symbol": "EURUSD"}]
    assert json.loads(output.read_text()) == result
    assert result["http_method_used"] == "GET"
    assert result["post_capability_present"] is False
    assert result["credentials_used"] is False
    assert result["request_sent"] is False


def test_quote_transport_constructs_only_canonical_get():
    calls = []

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_args): return None
        def read(self):
            return b'{"symbol":"EURUSD","bid":1,"ask":1,"mid":1,"timestamp":"x"}'

    def opener(request, **kwargs):
        calls.append((request, kwargs))
        return Response()

    result = fetch_latest_quote(
        base_url="http://127.0.0.1:8000/", symbol="EURUSD", opener=opener)
    request, kwargs = calls[0]
    assert request.get_method() == "GET"
    assert request.full_url == (
        "http://127.0.0.1:8000/api/v1/broker/price/latest?venue=ostium&symbol=EURUSD")
    assert kwargs == {"timeout": 5}
    assert result["symbol"] == "EURUSD"
