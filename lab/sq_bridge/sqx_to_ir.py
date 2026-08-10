#!/usr/bin/env python3
"""Tradueix el subset SQX verificat a l'IR canònic i reproduïble d'Alquímia."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from lab.sq_bridge.sqx_extract import extract
except ModuleNotFoundError:
    from sqx_extract import extract


def canonical_ir(contract: dict) -> dict:
    if contract.get("translation_status") != "SUPPORTED_SUBSET":
        raise ValueError(
            f"SQX fora del subset traduible: {contract.get('unsupported_nodes_or_formulas')}")
    plans = {direction: _execution_plan(entry, direction)
             for direction, entry in contract["entries"].items()}
    return {
        "schema_version": 1,
        "ir_type": "alquimia_strategy_ir",
        "translation_semantics": "exact_supported_subset",
        "strategy_id": contract["strategy_name"],
        "source_sqx_sha256": contract["source_sha256"],
        "source_strategy_xml_sha256": contract["strategy_xml_sha256"],
        "market": contract["market"],
        "execution": contract["execution"],
        "entries": contract["entries"],
        "trade_plans": plans,
        "entry_condition_counts": contract["entry_condition_counts"],
        "maximum_entry_conditions": contract["maximum_entry_conditions"],
        "exit_signals": contract["exit_signals"],
    }


def validate_executable_ir(ir: dict, *, require_stop_loss: bool = True) -> dict:
    """Fail closed on SQ semantics that cannot be deployed safely to Ostium."""
    execution = ir.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("Configuracio d'execucio SQ absent")
    if execution.get("exit_at_end_of_day") is not False:
        raise ValueError("ExitAtEndOfDay ha d'estar explicitament desactivat")
    if execution.get("exit_on_friday") is not False:
        raise ValueError("ExitOnFriday ha d'estar explicitament desactivat")
    for field in ("spread_in_sq", "slippage_in_sq"):
        value = execution.get(field)
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or float(value) != 0.0):
            raise ValueError(f"{field} ha de ser explicitament zero")
    if execution.get("commission_enabled") is not False:
        raise ValueError("La comissio SQ ha d'estar explicitament desactivada")
    if execution.get("swap_enabled") is not False:
        raise ValueError("El swap SQ ha d'estar explicitament desactivat")
    plans = ir.get("trade_plans")
    if not isinstance(plans, dict) or set(plans) != {"long", "short"}:
        raise ValueError("Plans de trade normalitzats absents")
    active = {direction: plan for direction, plan in plans.items() if plan is not None}
    if not active:
        raise ValueError("L'estrategia no te cap direccio executable")
    minimum_shifts = []
    for direction, plan in active.items():
        if (plan.get("entry_order") != "market_at_signal_bar_open"
                or plan.get("allow_duplicate_trades") is not False):
            raise ValueError(f"Entrada no executable per {direction}")
        stop = plan.get("stop_loss")
        if not isinstance(stop, dict) or "type" not in stop:
            raise ValueError(f"Stop no normalitzat per {direction}")
        if require_stop_loss and stop["type"] == "none":
            raise ValueError(f"Stop loss obligatori absent per {direction}")
        signal = ir.get("entries", {}).get(direction, {}).get("signal")
        if not isinstance(signal, dict):
            raise ValueError(f"Senyal absent per {direction}")
        shift = _validate_causal_signal(signal)
        if shift is not None:
            minimum_shifts.append(shift)
    return {
        "active_directions": sorted(active),
        "stop_loss_required": require_stop_loss,
        "stop_loss_present_all_directions": all(
            plan["stop_loss"]["type"] != "none" for plan in active.values()),
        "timed_session_exits_disabled": True,
        "sq_venue_costs_disabled": True,
        "causal_entry_signals": True,
        "minimum_market_data_shift": min(minimum_shifts) if minimum_shifts else None,
    }


_MARKET_DATA_NODES = {
    "Close", "High", "Low", "SMA", "EMA", "RSI", "ROC", "Highest", "Lowest",
}


def _validate_causal_signal(node: dict, inherited_shift: int = 0) -> int | None:
    op = node.get("op")
    params = node.get("params", {})
    own_shift = params.get("#Shift#", 0) or 0
    if not isinstance(own_shift, int) or isinstance(own_shift, bool) or own_shift < 0:
        raise ValueError(f"Shift invalid al node {op}")
    propagated = inherited_shift + (own_shift if op in {"IsRising", "IsFalling"} else 0)
    observed = []
    if op in _MARKET_DATA_NODES:
        effective = inherited_shift + own_shift
        if effective < 1:
            raise ValueError(f"Look-ahead: {op} usa la candle d'entrada Shift=0")
        observed.append(effective)
    if op == "IsMonthLastTradingDay":
        raise ValueError("IsMonthLastTradingDay no es causal al runtime actual")
    for child in node.get("children", []):
        value = _validate_causal_signal(child, propagated)
        if value is not None:
            observed.append(value)
    return min(observed) if observed else None


def _range_plan(value: object, label: str) -> dict:
    # SQ serialitza opcions desactivades segons el context com None, false o 0.
    if value is None or value is False or value == 0:
        return {"type": "none"}
    if not isinstance(value, dict) or not isinstance(value.get("formula"), str):
        raise ValueError(f"Formula d'execucio invalida: {label}")
    formula, params = value["formula"], value.get("params", {})
    if formula.endswith(".None"):
        return {"type": "none"}
    amount = params.get("#Value#")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValueError(f"Valor d'execucio invalid: {label}")
    if formula == "SQ.Formulas.SLPT.ATRBasedValue":
        period = params.get("#AtrPeriod#")
        if not isinstance(period, int) or isinstance(period, bool) or period < 1:
            raise ValueError(f"Periode ATR invalid: {label}")
        return {"type": "atr", "multiple": float(amount), "period": period}
    if formula == "SQ.Formulas.SLPT.PctValue":
        return {"type": "percent", "percent": float(amount)}
    raise ValueError(f"Formula d'execucio no normalitzable: {formula}")


def _execution_plan(entry: dict | None, direction: str) -> dict | None:
    if entry is None:
        return None
    action = entry["action"]
    if action.get("op") != "EnterAtMarket":
        raise ValueError("El pla executable requereix EnterAtMarket")
    params = action.get("params", {})
    declared = params.get("#Direction#")
    expected = 1 if direction == "long" else -1
    if declared is not None and declared != expected:
        raise ValueError("Direccio SQ inconsistent amb la regla")
    if params.get("#AllowDuplicateTrades#", False) is not False:
        raise ValueError("Trades duplicats no son executables al subset")
    exit_after = params.get("#ExitAfterBars.ExitAfterBars#", 0) or 0
    if not isinstance(exit_after, int) or isinstance(exit_after, bool) or exit_after < 0:
        raise ValueError("ExitAfterBars invalid")
    for key in ("#MoveSL2BE.MoveSL2BE#", "#TrailingStop.TrailingStop#"):
        if _range_plan(params.get(key), key)["type"] != "none":
            raise ValueError(f"Gestio dinamica no executable: {key}")
    return {
        "entry_order": "market_at_signal_bar_open",
        "allow_duplicate_trades": False,
        "exit_after_bars": exit_after,
        "stop_loss": _range_plan(params.get("#StopLoss.StopLoss#"), "stop_loss"),
        "profit_target": _range_plan(
            params.get("#ProfitTarget.ProfitTarget#"), "profit_target"),
    }


def translate(sqx_path: Path, output_path: Path) -> dict:
    result = canonical_ir(extract(sqx_path))
    validate_executable_ir(result)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = translate(args.sqx, args.output)
    print(json.dumps({"strategy_id": result["strategy_id"],
                      "maximum_entry_conditions": result["maximum_entry_conditions"]}, indent=2))


if __name__ == "__main__":
    main()
