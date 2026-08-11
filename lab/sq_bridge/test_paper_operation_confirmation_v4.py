import pytest

from lab.sq_bridge.paper_operation_confirmation_v4 import (
    accept_pending_ack, observe_operation, reconcile_position,
)


def template():
    return {
        "decision": "PASS_FRESH_QUOTE_REVALIDATION",
        "candidate_id": "candidate", "paper_request_ready": True,
        "portfolio_admission_required": False, "request_sent": False,
        "portfolio_admission": {
            "decision": "PASS_PORTFOLIO_ENTRY_ADMISSION",
            "candidate_id": "candidate", "order_sent": False,
        },
        "brokerage_async_contract": {"initial_http_status": 202},
        "request_body": {"client_order_id": "alq4-id", "symbol": "EURUSD",
                         "side": "long", "collateral": 60, "leverage": 5,
                         "sl_price": 1.14},
        "entry_notional_envelope": {
            "conservative_effective_notional_usdc": 299.2,
            "gross_notional_upper_bound_usdc": 300,
        },
    }


def ack():
    return {"success": True, "pending": True, "operation_id": "abcdef123456",
            "position_id": "", "executed_price": 0, "executed_size": 0,
            "tx_hash": ""}


def operation(status="confirmed"):
    return {"operation_id": "abcdef123456", "kind": "open", "venue": "ostium",
            "symbol": "EURUSD", "status": status,
            "position_id": "ostium:2:0" if status == "confirmed" else "",
            "tx_hash": "0xabc", "error": None}


def test_202_is_tracking_state_not_a_fill():
    result = accept_pending_ack(template=template(), http_status=202, ack=ack())
    assert result["decision"] == "WAIT_OPERATION_CONFIRMATION"
    assert result["request_sent"] is True
    assert result["fill_confirmed"] is False


def test_pending_ack_rejects_bypassed_or_foreign_portfolio_admission():
    missing = template()
    missing.pop("portfolio_admission")
    with pytest.raises(ValueError, match="admissio"):
        accept_pending_ack(template=missing, http_status=202, ack=ack())
    foreign = template()
    foreign["portfolio_admission"] = {
        **foreign["portfolio_admission"], "candidate_id": "other"}
    with pytest.raises(ValueError, match="admissio"):
        accept_pending_ack(template=foreign, http_status=202, ack=ack())


def test_confirmation_normalizes_brokerage_double_venue_prefix():
    tracking = accept_pending_ack(template=template(), http_status=202, ack=ack())
    value = operation()
    value["position_id"] = "ostium:ostium:2:0"
    result = observe_operation(tracking=tracking, operation=value)
    assert result["decision"] == "WAIT_POSITION_RECONCILIATION"
    assert result["position_id"] == "ostium:2:0"
    assert result["fill_confirmed"] is False


def test_incomplete_legacy_position_shape_blocks_instead_of_guessing():
    tracking = accept_pending_ack(template=template(), http_status=202, ack=ack())
    confirmed = observe_operation(tracking=tracking, operation=operation())
    result = reconcile_position(confirmation=confirmed, positions_payload={"positions": [{
        "position_id": "ostium:ostium:2:0", "symbol": "EURUSD", "side": "LONG",
        "notional": 299.5, "open_price": 1.15, "sl_price": 1.14,
    }]})
    assert result["decision"] == "BLOCK_INCOMPLETE_POSITION_RECONCILIATION"
    assert result["missing_position_fields"] == ["collateral", "leverage"]
    assert result["fill_confirmed"] is False


def test_complete_on_venue_position_confirms_only_inside_frozen_envelope():
    tracking = accept_pending_ack(template=template(), http_status=202, ack=ack())
    confirmed = observe_operation(tracking=tracking, operation=operation())
    row = {"position_id": "ostium:ostium:2:0", "symbol": "EURUSD", "side": "LONG",
           "collateral": 59.9, "leverage": 5, "notional": 299.5,
           "open_price": 1.15, "sl_price": 1.14}
    result = reconcile_position(
        confirmation=confirmed, positions_payload={"positions": [row]})
    assert result["decision"] == "PASS_CONFIRMED_PAPER_FILL"
    assert result["fill_confirmed"] is True
    assert result["confirmed_effective_notional_usdc"] == 299.5
    assert result["notional_underfill_usdc"] == pytest.approx(.5)
    row["notional"] = 301
    row["collateral"] = 60.2
    with pytest.raises(ValueError, match="envolupant"):
        reconcile_position(confirmation=confirmed,
                           positions_payload={"positions": [row]})


def test_error_and_foreign_operation_fail_closed():
    tracking = accept_pending_ack(template=template(), http_status=202, ack=ack())
    failed = operation("error")
    failed["error"] = "venue rejected"
    result = observe_operation(tracking=tracking, operation=failed)
    assert result["decision"] == "REJECT_OPERATION_ERROR"
    foreign = operation()
    foreign["operation_id"] = "000000000000"
    with pytest.raises(ValueError, match="aliena"):
        observe_operation(tracking=tracking, operation=foreign)
