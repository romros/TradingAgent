#!/usr/bin/env python3
"""Map a verified Alquimia paper signal to an inert BrokerageService request.

The result is deliberately not sendable: Ostium executes at its current quote,
so a separate pre-send quote/stop revalidation is required after this mapping.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from lab.sq_bridge.paper_package_artifact_v4 import verify_package
from lab.sq_bridge.small_account_artifact_v4 import select_cost_envelope


BROKERAGE_ENDPOINT = "/api/v1/broker/orders/open"
BROKERAGE_API_MAX_LEVERAGE = 100.0
DEFAULT_MARKET_REGISTRY = Path(__file__).with_name("ostium_markets.json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: object, label: str) -> float:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError(f"{label} invalid")
    return float(value)


def _execution_market(pair_id: str, registry_path: Path) -> tuple[str, str]:
    registry = json.loads(registry_path.read_text())
    matches = [value for value in registry.get("markets", {}).values()
               if value.get("ostium_pair") == pair_id]
    if len(matches) != 1:
        raise ValueError("mapping Ostium/BrokerageService absent o ambigu")
    market = matches[0]
    symbol = str(market.get("bs_symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("bs_symbol absent del registre de mercats")
    return symbol, _sha(registry_path)


def _client_order_id(config: dict, instruction: dict) -> str:
    identity = "|".join((
        str(config["campaign_id"]), str(config["candidate_id"]),
        str(instruction["signal_timestamp"]), str(instruction["side"]),
        str(config["strategy_ir_sha256"]),
    ))
    return "alq4-" + hashlib.sha256(identity.encode()).hexdigest()[:32]


def _entry_notional_envelope(*, gross_collateral: float, leverage: float,
                             costs: dict) -> dict:
    """Bound entry notional without unsafe fee gross-up.

    The zero-fee value is a hard upper bound.  The lower estimate uses the
    largest opening fee observed in the frozen sample plus the locked oracle
    amount.  Exact matching remains a paper-fill measurement, not an assumed
    property of a stale venue snapshot.
    """
    debit = costs.get("entry_debit") or {}
    if debit.get("sizing_policy") != "never gross up from a stale fee observation":
        raise ValueError("semantica de debit d'entrada absent")
    open_fee_bps = _finite(
        debit.get("maximum_observed_open_fee_bps"), "opening fee observada")
    oracle = _finite(debit.get("oracle_locked_usdc"), "oracle bloquejat")
    if open_fee_bps < 0 or oracle < 0:
        raise ValueError("debit d'entrada negatiu")
    gross_notional = gross_collateral * leverage
    opening_fee = gross_notional * open_fee_bps / 10_000
    effective_collateral = gross_collateral - opening_fee - oracle
    if effective_collateral <= 0:
        raise ValueError("debit d'entrada consumeix tot el collateral")
    return {
        "gross_notional_upper_bound_usdc": gross_notional,
        "conservative_opening_fee_usdc": opening_fee,
        "oracle_locked_usdc": oracle,
        "conservative_effective_collateral_usdc": effective_collateral,
        "conservative_effective_notional_usdc": effective_collateral * leverage,
        "underfill_usdc": gross_notional - effective_collateral * leverage,
    }


def build_order_template(*, config_path: Path, instruction: dict,
                         operational_max_leverage: float,
                         registry_path: Path = DEFAULT_MARKET_REGISTRY) -> dict:
    """Build an exact but inert API template; never performs I/O beyond files."""
    config_path = config_path.resolve()
    registry_path = registry_path.resolve()
    config = json.loads(config_path.read_text())
    if not verify_package(config, config_path):
        raise ValueError("paquet paper Alquimia invalid")
    if instruction.get("decision") == "NO_PAPER_SIGNAL":
        return {
            "schema_version": 1, "decision": "NO_ORDER_TEMPLATE",
            "request_sent": False, "candidate_id": config["candidate_id"],
            "signal_timestamp": instruction.get("signal_timestamp"),
        }
    if (instruction.get("decision") != "PASS_PAPER_SIGNAL_INSTRUCTION"
            or instruction.get("order_sent") is not False):
        raise ValueError("instruccio paper no valida o ja marcada com enviada")
    if (instruction.get("candidate_id") != config["candidate_id"]
            or instruction.get("ostium_pair_id") != config["ostium_pair_id"]
            or instruction.get("strategy_ir_sha256") != config["strategy_ir_sha256"]):
        raise ValueError("lineage de la instruccio paper inconsistent")
    side = instruction.get("side")
    if side not in {"long", "short"}:
        raise ValueError("side no executable")
    leverage = _finite(instruction.get("selected_leverage"), "leverage")
    collateral = _finite(instruction.get("collateral_usdc"), "collateral")
    notional = _finite(instruction.get("position_notional_usdc"), "nocional")
    entry = _finite(instruction.get("entry_price"), "preu de senyal")
    stop = _finite(instruction.get("stop_price"), "stop")
    runtime_cap = _finite(operational_max_leverage, "limit operatiu")
    package_execution_cap = _finite(
        config.get("execution_max_leverage"), "limit executable del paquet")
    if package_execution_cap != BROKERAGE_API_MAX_LEVERAGE:
        raise ValueError("contracte de leverage del paquet no coincideix amb BrokerageService")
    if leverage < 1 or leverage != int(leverage):
        raise ValueError("Ostium adapter requereix leverage enter")
    effective_cap = min(package_execution_cap, runtime_cap)
    if leverage > effective_cap:
        raise ValueError(
            f"leverage {leverage:g}x supera el limit executable {effective_cap:g}x")
    if collateral <= 0 or notional <= 0 or not math.isclose(
            collateral * leverage, notional, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("collateral, leverage i nocional no quadren")
    if entry <= 0 or stop <= 0 or (side == "long" and stop >= entry) \
            or (side == "short" and stop <= entry):
        raise ValueError("stop incompatible amb side/preu de senyal")
    cost_path = (config_path.parent / config["cost_model_path"]).resolve()
    if not cost_path.is_file() or _sha(cost_path) != config["cost_model_sha256"]:
        raise ValueError("model de costos absent o manipulat")
    entry_notional = _entry_notional_envelope(
        gross_collateral=collateral, leverage=leverage,
        costs=json.loads(cost_path.read_text()))
    if not math.isclose(entry_notional["gross_notional_upper_bound_usdc"], notional,
                        rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("limit superior de nocional inconsistent")
    symbol, registry_sha = _execution_market(config["ostium_pair_id"], registry_path)
    body = {
        "venue": "ostium", "symbol": symbol, "side": side,
        "collateral": collateral, "leverage": leverage,
        "sl_price": stop, "tp_price": None,
        "client_order_id": _client_order_id(config, instruction),
    }
    return {
        "schema_version": 1,
        "decision": "PREPARED_INERT_ORDER_TEMPLATE",
        "candidate_id": config["candidate_id"],
        "signal_timestamp": instruction["signal_timestamp"],
        "method": "POST", "endpoint": BROKERAGE_ENDPOINT,
        "request_body": body,
        "brokerage_api_max_leverage": BROKERAGE_API_MAX_LEVERAGE,
        "operational_max_leverage": runtime_cap,
        "effective_execution_max_leverage": effective_cap,
        "ostium_venue_max_leverage": config["venue_max_leverage"],
        "market_registry_path": str(registry_path),
        "market_registry_sha256": registry_sha,
        "signal_entry_price": entry,
        "position_notional_usdc": notional,
        "entry_notional_semantics": "target_is_zero_fee_upper_bound_not_guaranteed_fill",
        "entry_notional_envelope": entry_notional,
        "risk_budget_usdc": _finite(instruction.get("risk_budget_usdc"), "pressupost de risc"),
        "initial_stop_distance_pct": _finite(
            instruction.get("initial_stop_distance_pct"), "distancia inicial de stop"),
        "paper_execution_policy": config["paper_execution_policy"],
        "cost_model_path": str(cost_path),
        "cost_model_sha256": config["cost_model_sha256"],
        "fresh_quote_required": True,
        "stop_direction_revalidation_required": True,
        "request_sent": False,
        "signer_enabled": False,
        "live_authorized": False,
    }


def revalidate_fresh_quote(*, template: dict, quote: dict,
                           observed_at: datetime) -> dict:
    """Apply preregistered quote gates without sending the prepared request."""
    if (template.get("decision") != "PREPARED_INERT_ORDER_TEMPLATE"
            or template.get("request_sent") is not False
            or template.get("fresh_quote_required") is not True):
        raise ValueError("plantilla inert no revalidable")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at ha de tenir timezone")
    policy = template.get("paper_execution_policy") or {}
    if (policy.get("maximum_live_spread_policy")
            != "stress_variable_roundtrip_bps_envelope"
            or policy.get("entry_reference_price") != "brokerage_service_ostium_mid"
            or policy.get("require_runtime_risk_at_or_below_signal_budget") is not True):
        raise ValueError("politica de quote paper invalida")
    try:
        quote_time = datetime.fromisoformat(str(quote["timestamp"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("timestamp del quote invalid") from exc
    if quote_time.tzinfo is None or quote_time.utcoffset() is None:
        raise ValueError("timestamp del quote sense timezone")
    age = (observed_at - quote_time).total_seconds()
    if age > _finite(policy.get("maximum_quote_age_seconds"), "edat maxima quote"):
        raise ValueError("quote caducat")
    if age < -_finite(policy.get("maximum_future_clock_skew_seconds"), "skew maxim quote"):
        raise ValueError("quote massa futur")
    body = template["request_body"]
    if str(quote.get("symbol", "")).upper() != body["symbol"]:
        raise ValueError("symbol del quote no coincideix")
    bid, ask, mid = (_finite(quote.get(key), f"quote {key}")
                     for key in ("bid", "ask", "mid"))
    if bid <= 0 or ask <= 0 or mid <= 0 or not bid <= mid <= ask:
        raise ValueError("bid/ask/mid incoherents")
    side, stop = body["side"], _finite(body["sl_price"], "stop")
    if (side == "long" and stop >= mid) or (side == "short" and stop <= mid):
        raise ValueError("stop ha quedat al costat incorrecte del quote")
    signal_entry = _finite(template["signal_entry_price"], "preu de senyal")
    initial_stop_pct = _finite(
        template["initial_stop_distance_pct"], "stop inicial")
    deviation_bps = abs(mid / signal_entry - 1) * 10_000
    maximum_deviation_bps = initial_stop_pct * 100 * _finite(
        policy.get("maximum_signal_deviation_fraction_of_initial_stop"),
        "fraccio maxima de desviacio")
    if deviation_bps > maximum_deviation_bps:
        raise ValueError("quote massa lluny del preu de senyal")
    notional = _finite(template["position_notional_usdc"], "nocional")
    runtime_risk = notional * abs(mid - stop) / mid
    risk_budget = _finite(template["risk_budget_usdc"], "pressupost de risc")
    if runtime_risk > risk_budget + 1e-9:
        raise ValueError("risc runtime supera el pressupost del senyal")
    cost_path = Path(template["cost_model_path"])
    if not cost_path.is_file() or _sha(cost_path) != template["cost_model_sha256"]:
        raise ValueError("model de costos absent o manipulat")
    costs = json.loads(cost_path.read_text())
    _, variable, _, _ = select_cost_envelope(costs, notional)
    spread_bps = (ask - bid) / mid * 10_000
    if spread_bps > variable["stress"]:
        raise ValueError("spread live supera l'envolupant stress")
    return {
        **template,
        "decision": "PASS_FRESH_QUOTE_REVALIDATION",
        "quote": {"symbol": body["symbol"], "bid": bid, "ask": ask,
                  "mid": mid, "timestamp": quote_time.isoformat()},
        "quote_observed_at": observed_at.isoformat(),
        "quote_age_seconds": age,
        "signal_deviation_bps": deviation_bps,
        "maximum_signal_deviation_bps": maximum_deviation_bps,
        "live_spread_bps": spread_bps,
        "stress_spread_envelope_bps": variable["stress"],
        "runtime_stop_risk_usdc": runtime_risk,
        "paper_request_ready": True,
        "fresh_quote_required": False,
        "request_sent": False,
        "signer_enabled": False,
        "live_authorized": False,
    }
