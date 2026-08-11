#!/usr/bin/env python3
"""Pure fail-closed confirmation of an asynchronous BrokerageService paper open.

This module performs no HTTP requests and cannot submit an order.  A future
runner supplies the already observed 202 acknowledgement, operation snapshot
and positions snapshot.  Only an on-venue position with complete sizing fields
can become a confirmed paper fill.
"""
from __future__ import annotations

import math
from typing import Any


def _number(value: object, label: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(f"{label} invalid")
    return float(value)


def _canonical_position_id(value: object) -> str:
    raw = str(value or "").strip().lower()
    while raw.startswith("ostium:ostium:"):
        raw = raw[len("ostium:"):]
    return raw


def accept_pending_ack(*, template: dict[str, Any], http_status: int,
                       ack: dict[str, Any]) -> dict[str, Any]:
    if (template.get("decision") != "PASS_FRESH_QUOTE_REVALIDATION"
            or template.get("paper_request_ready") is not True
            or template.get("request_sent") is not False):
        raise ValueError("template fresc no autoritzat per tracking")
    contract = template.get("brokerage_async_contract") or {}
    if (http_status != contract.get("initial_http_status")
            or ack.get("success") is not True or ack.get("pending") is not True):
        raise ValueError("ack inicial no compleix el contracte 202 pending")
    operation_id = ack.get("operation_id")
    if (not isinstance(operation_id, str) or len(operation_id) != 12
            or any(character not in "0123456789abcdef" for character in operation_id)):
        raise ValueError("operation_id invalid")
    if any(ack.get(field) not in (None, "", 0, 0.0)
           for field in ("position_id", "executed_price", "executed_size", "tx_hash")):
        raise ValueError("un ack pending no pot afirmar dades d'execucio")
    return {
        "schema_version": 1,
        "decision": "WAIT_OPERATION_CONFIRMATION",
        "operation_id": operation_id,
        "client_order_id": template["request_body"]["client_order_id"],
        "symbol": template["request_body"]["symbol"],
        "side": template["request_body"]["side"],
        "template": template,
        "request_sent": True,
        "fill_confirmed": False,
        "paper_only": True,
        "live_authorized": False,
    }


def observe_operation(*, tracking: dict[str, Any],
                      operation: dict[str, Any]) -> dict[str, Any]:
    if tracking.get("decision") != "WAIT_OPERATION_CONFIRMATION":
        raise ValueError("tracking no espera operacio")
    if (operation.get("operation_id") != tracking.get("operation_id")
            or operation.get("kind") != "open"
            or str(operation.get("venue", "")).lower() != "ostium"
            or str(operation.get("symbol", "")).upper() != tracking.get("symbol")):
        raise ValueError("operacio aliena o inconsistent")
    status = operation.get("status")
    if status in {"in_progress", "pending"}:
        return {**tracking, "operation_status": status}
    if status == "error":
        error = operation.get("error")
        if not isinstance(error, str) or not error.strip():
            raise ValueError("operacio error sense diagnostic")
        return {**tracking, "decision": "REJECT_OPERATION_ERROR",
                "operation_status": status, "operation_error": error,
                "fill_confirmed": False}
    if status != "confirmed":
        raise ValueError("estat d'operacio desconegut")
    position_id = _canonical_position_id(operation.get("position_id"))
    if not position_id.startswith("ostium:") or position_id.count(":") != 2:
        raise ValueError("operacio confirmada sense position_id Ostium")
    return {
        **tracking,
        "decision": "WAIT_POSITION_RECONCILIATION",
        "operation_status": "confirmed",
        "position_id": position_id,
        "tx_hash": str(operation.get("tx_hash") or ""),
        "fill_confirmed": False,
    }


def reconcile_position(*, confirmation: dict[str, Any],
                       positions_payload: dict[str, Any]) -> dict[str, Any]:
    if confirmation.get("decision") != "WAIT_POSITION_RECONCILIATION":
        raise ValueError("confirmacio no espera posicio")
    rows = positions_payload.get("positions")
    if not isinstance(rows, list):
        raise ValueError("payload de posicions invalid")
    matches = [row for row in rows if isinstance(row, dict)
               and _canonical_position_id(row.get("position_id"))
               == confirmation["position_id"]]
    if len(matches) != 1:
        return {**confirmation, "decision": "WAIT_POSITION_RECONCILIATION",
                "matching_positions": len(matches), "fill_confirmed": False}
    row = matches[0]
    template = confirmation["template"]
    body = template["request_body"]
    side = str(row.get("side", "")).lower()
    side = {"long": "long", "short": "short"}.get(side)
    if str(row.get("symbol", "")).upper() != body["symbol"] or side != body["side"]:
        raise ValueError("identitat de posicio no coincideix amb l'ordre")
    required = ("collateral", "leverage", "notional", "open_price", "sl_price")
    missing = [field for field in required if row.get(field) is None]
    if missing:
        return {
            **confirmation,
            "decision": "BLOCK_INCOMPLETE_POSITION_RECONCILIATION",
            "missing_position_fields": missing,
            "brokerage_contract_gap": (
                "GET /positions must expose on-venue collateral and leverage"),
            "fill_confirmed": False,
        }
    collateral = _number(row["collateral"], "collateral confirmat")
    leverage = _number(row["leverage"], "leverage confirmat")
    notional = _number(row["notional"], "nocional confirmat")
    open_price = _number(row["open_price"], "preu confirmat")
    stop = _number(row["sl_price"], "stop confirmat")
    if min(collateral, leverage, notional, open_price, stop) <= 0:
        raise ValueError("posicio confirmada fora de domini")
    if leverage != body["leverage"]:
        raise ValueError("leverage on-venue no coincideix")
    if not math.isclose(collateral * leverage, notional, rel_tol=1e-8, abs_tol=1e-8):
        raise ValueError("collateral i nocional on-venue no quadren")
    envelope = template["entry_notional_envelope"]
    lower = _number(envelope["conservative_effective_notional_usdc"], "limit inferior")
    upper = _number(envelope["gross_notional_upper_bound_usdc"], "limit superior")
    if not lower - 1e-8 <= notional <= upper + 1e-8:
        raise ValueError("nocional on-venue fora de l'envolupant congelada")
    if not math.isclose(stop, body["sl_price"], rel_tol=1e-8, abs_tol=1e-8):
        raise ValueError("stop on-venue no coincideix")
    return {
        **confirmation,
        "decision": "PASS_CONFIRMED_PAPER_FILL",
        "confirmed_position": row,
        "confirmed_effective_notional_usdc": notional,
        "confirmed_collateral_usdc": collateral,
        "confirmed_leverage": leverage,
        "notional_underfill_usdc": upper - notional,
        "fill_confirmed": True,
        "paper_only": True,
        "live_authorized": False,
    }
