#!/usr/bin/env python3
"""Map a verified Alquimia paper signal to an inert BrokerageService request.

The result is deliberately not sendable: Ostium executes at its current quote,
so a separate pre-send quote/stop revalidation is required after this mapping.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from lab.sq_bridge.paper_package_artifact_v4 import verify_package


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
        "fresh_quote_required": True,
        "stop_direction_revalidation_required": True,
        "request_sent": False,
        "signer_enabled": False,
        "live_authorized": False,
    }
