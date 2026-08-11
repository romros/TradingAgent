#!/usr/bin/env python3
"""Extreu un contracte JSON reproduible d'un SQX limitat al subset Alquimia."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SUPPORTED_SIGNAL_NODES = {
    "AND", "Not", "IsRising", "IsFalling", "CrossesAbove", "CrossesBelow",
    "IsGreater", "IsLower", "Close", "Low", "High", "SMA", "EMA", "RSI",
    "ROC", "Highest", "Lowest", "BarDayOfMonth", "BarDayOfWeekIs", "IsMonthFirstTradingDay",
    "IsMonthLastTradingDay", "Number", "Boolean",
}
SUPPORTED_ENTRY = {"EnterAtMarket"}
SUPPORTED_FORMULAS = {
    "SQ.Formulas.Size.UseGlobalMM", "SQ.Formulas.SLPT.ATRBasedValue",
    "SQ.Formulas.SLPT.PctValue", "SQ.Formulas.SLPT.None",
    "SQ.Formulas.Range.None", "SQ.Formulas.RangeLevel.None",
}


def _value(element: ET.Element) -> str | int | float | bool | None:
    raw = (element.text or "").strip()
    if raw == "": return None
    if raw.lower() in {"true", "false"}: return raw.lower() == "true"
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return raw


def _item(element: ET.Element) -> dict:
    result = {"op": element.attrib["key"]}
    params = {}
    for param in element.findall("Param"):
        formula = param.find("Formula")
        if formula is None:
            params[param.attrib["key"]] = _value(param)
        else:
            params[param.attrib["key"]] = {
                "formula": formula.attrib["key"],
                "params": {child.attrib["key"]: _value(child) for child in formula.findall("Param")},
            }
    if params: result["params"] = params
    children = []
    for block in element.findall("Block"):
        child = block.find("Item")
        if child is not None: children.append(_item(child))
    # AND generat pot contenir Item directes en lloc de Block.
    children.extend(_item(child) for child in element.findall("Item"))
    if children: result["children"] = children
    return result


def _ops(node: dict) -> set[str]:
    return {node["op"]} | {op for child in node.get("children", []) for op in _ops(child)}


def _nodes(node: dict):
    yield node
    for child in node.get("children", []):
        yield from _nodes(child)


def _entry_condition_count(node: dict) -> int:
    """Compta predicats d'entrada SQ, no els indicadors que els componen.

    StrategyQuant limita les condicions per gràfic. Un AND és un contenidor de
    regles i, per tant, suma els seus fills; qualsevol altre node arrel és un
    únic predicat encara que contingui operands (SMA, Number, Close...).
    """
    if node.get("op") == "AND":
        children = node.get("children", [])
        if not children:
            raise ValueError("Signal AND sense condicions")
        return sum(_entry_condition_count(child) for child in children)
    return 1


def _entry_gate(item: ET.Element) -> dict:
    op = item.attrib.get("key")
    # Older SQX variants (and some hand-built fixtures) wrap a BooleanVariable
    # as an unkeyed Item containing the variable Param directly.  Newer SQX
    # writes an explicit Item key="BooleanVariable".  Both mean the same gate.
    if op is None:
        variable = item.find("./Param[@key='#Variable#']")
        if variable is not None:
            value = str(_value(variable))
            if not value:
                raise ValueError("BooleanVariable d'entrada sense UUID")
            return {"op": "var", "id": value}
        children = item.findall("./Item")
        if len(children) == 1:
            return _entry_gate(children[0])
        raise ValueError("Gate d'entrada embolcallat no interpretable")
    if op == "BooleanVariable":
        variable = item.find("./Param[@key='#Variable#']")
        value = str(_value(variable)) if variable is not None else ""
        if not value:
            raise ValueError("BooleanVariable d'entrada sense UUID")
        return {"op": "var", "id": value}
    if op not in {"AND", "Not"}:
        raise ValueError(f"Gate d'entrada no suportat: {op}")
    children = [block.find("Item") for block in item.findall("Block")]
    children.extend(item.findall("Item"))
    if any(child is None for child in children) or not children:
        raise ValueError(f"Gate {op} sense fills")
    if op == "Not" and len(children) != 1:
        raise ValueError("Gate Not requereix un fill")
    return {"op": op.lower(), "children": [_entry_gate(child) for child in children]}


def _gate_ids(gate: dict) -> set[str]:
    if gate["op"] == "var":
        return {gate["id"]}
    return {value for child in gate.get("children", []) for value in _gate_ids(child)}


def _resolve_gate(gate: dict, signals: dict[str, dict]) -> dict:
    if gate["op"] == "var":
        if gate["id"] not in signals:
            raise ValueError(f"Regla d'entrada referencia un signal inexistent: {gate['id']}")
        return copy.deepcopy(signals[gate["id"]])
    op = "AND" if gate["op"] == "and" else "Not"
    return {"op": op, "children": [_resolve_gate(child, signals)
                                     for child in gate["children"]]}


def _setting(root: ET.Element, key: str):
    node = root.find(f".//*[@key='{key}']")
    if node is None:
        node = root.find(f".//{key}")
    return _value(node) if node is not None else None


def _bool_attribute(element: ET.Element | None, key: str) -> bool | None:
    if element is None or key not in element.attrib:
        return None
    raw = element.attrib[key].strip().lower()
    if raw not in {"true", "false"}:
        return None
    return raw == "true"


def _instrument_info(settings: ET.Element, symbol: object) -> ET.Element | None:
    """Return the exact instrument snapshot used by the SQ result."""
    matches = [node.find("InstrumentInfo") for node in settings.findall(".//SymbolInfo")
               if node.attrib.get("symbolName") == symbol]
    matches = [node for node in matches if node is not None]
    if len(matches) == 1:
        return matches[0]
    return None


def _embedded_xml_attribute(element: ET.Element | None, key: str) -> ET.Element | None:
    if element is None or not element.attrib.get(key):
        return None
    try:
        return ET.fromstring(element.attrib[key])
    except ET.ParseError:
        return None


def _commission_contract(instrument: ET.Element | None) -> dict:
    method = _embedded_xml_attribute(instrument, "commissions")
    if method is None or method.tag != "Method":
        return {"commission_enabled": None, "commission_method": None,
                "commission_value": None}
    use = _bool_attribute(method, "use")
    method_type = method.attrib.get("type")
    value_node = method.find("./Params/Param[@key='Commission']")
    value = _value(value_node) if value_node is not None else None
    enabled = None if use is None or method_type is None else use and method_type != "None"
    return {"commission_enabled": enabled, "commission_method": method_type,
            "commission_value": value}


def _swap_enabled(settings: ET.Element, instrument: ET.Element | None) -> bool | None:
    # SettingsMap is the authoritative effective result setting. InstrumentInfo
    # is only a fallback for older SQX variants.
    swap = settings.find(".//SettingsMap/Swap/Swap")
    if swap is None:
        swap = _embedded_xml_attribute(instrument, "swap")
    return _bool_attribute(swap, "use")


def extract(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        required = {"strategy_Portfolio.xml", "settings.xml", "version.txt"}
        missing = sorted(required - names)
        if missing: raise ValueError(f"SQX incomplet: {missing}")
        strategy_raw = archive.read("strategy_Portfolio.xml")
        settings_raw = archive.read("settings.xml")
    strategy = ET.fromstring(strategy_raw); settings = ET.fromstring(settings_raw)
    signal_nodes = strategy.findall(".//Rule[@type='Signal']/signals/signal")
    signals = {}
    for signal in signal_nodes:
        item = signal.find("Item")
        if item is None: raise ValueError("Signal sense Item")
        signals[signal.attrib["variable"]] = _item(item)
    rules = {rule.attrib.get("name"): rule for rule in strategy.findall(".//Event[@key='OnBarUpdate']/Rule")}
    entries = {}
    formulas = set()
    unsupported = set()
    for direction, rule_name in (("long", "Long entry"), ("short", "Short entry")):
        rule = rules.get(rule_name)
        if rule is None: raise ValueError(f"Falta {rule_name}")
        action = rule.find("./Then/Item")
        # Els projectes directionals de SQ conserven la regla oposada amb Then buit.
        if action is None:
            entries[direction] = None
            continue
        condition = rule.find("./If/Item")
        if condition is None: raise ValueError(f"{rule_name} no interpretable")
        gate = _entry_gate(condition)
        used_ids = sorted(_gate_ids(gate))
        signal = _resolve_gate(gate, signals)
        unsupported.update(_ops(signal) - SUPPORTED_SIGNAL_NODES)
        if any(node["op"] in {"SMA", "EMA", "RSI", "ROC"}
               and node.get("params", {}).get("#ComputedFrom#", 0) != 0
               for node in _nodes(signal)):
            unsupported.add("NON_CLOSE_COMPUTED_FROM")
        if any(node["op"] in {"Highest", "Lowest"}
               and node.get("params", {}).get("#ComputedFrom#", 0)
                   not in {0, 1, 2, 3, 4, 5, 6}
               for node in _nodes(signal)):
            unsupported.add("INVALID_PRICE_COMPUTED_FROM")
        if action.attrib["key"] not in SUPPORTED_ENTRY: unsupported.add(action.attrib["key"])
        action_ast = _item(action)
        for formula in action.findall(".//Formula"):
            formulas.add(formula.attrib["key"])
        entries[direction] = {
            "signal_variable_id": (gate["id"] if gate["op"] == "var" else None),
            "signal_variable_ids_used": used_ids,
            "entry_gate": gate,
            "signal": signal,
            "action": action_ast,
            "condition_count": _entry_condition_count(signal),
        }
    unsupported.update(formulas - SUPPORTED_FORMULAS)
    exit_signal_values = {}
    for signal_id, node in signals.items():
        if signal_id in {"33333333-1111-2222-3333-333333333333", "33333333-2222-2222-3333-333333333333"}:
            exit_signal_values[signal_id] = node
            if node != {"op": "Boolean", "params": {"#Value#": False}}:
                unsupported.add("NON_FALSE_EXIT_SIGNAL")
    entry_condition_counts = {
        direction: entry["condition_count"] if entry is not None else 0
        for direction, entry in entries.items()
    }
    symbol = _setting(settings, "Symbol")
    instrument = _instrument_info(settings, symbol)
    commission = _commission_contract(instrument)
    spread = None
    point_value = None
    order_size_multiplier = None
    tick_step = None
    if instrument is not None and "defaultSpread" in instrument.attrib:
        try:
            spread = float(instrument.attrib["defaultSpread"])
        except ValueError:
            pass
    if instrument is not None:
        for key, default, assign in (
                ("pointValue", None, "point_value"),
                ("orderSizeMultiplier", "1", "order_size_multiplier"),
                ("tickStep", None, "tick_step")):
            raw = instrument.attrib.get(key, default)
            try:
                parsed = float(raw) if raw is not None else None
            except ValueError:
                parsed = None
            if assign == "point_value":
                point_value = parsed
            elif assign == "order_size_multiplier":
                order_size_multiplier = parsed
            else:
                tick_step = parsed
    contract = {
        "schema_version": 1,
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "strategy_xml_sha256": hashlib.sha256(strategy_raw).hexdigest(),
        "strategy_name": _setting(settings, "StrategyName"),
        "market": {"symbol": symbol, "timeframe": _setting(settings, "Timeframe")},
        "execution": {
            "exit_at_end_of_day": _setting(settings, "ExitAtEndOfDay.ExitAtEndOfDay"),
            "eod_exit_time_hhmm": _setting(settings, "ExitAtEndOfDay.EODExitTime"),
            "exit_on_friday": _setting(settings, "ExitOnFriday.ExitOnFriday"),
            "friday_exit_time_hhmm": _setting(settings, "ExitOnFriday.FridayExitTime"),
            "dont_trade_on_weekends": _setting(
                settings, "DontTradeOnWeekends.DontTradeOnWeekends"),
            "weekend_friday_close_hhmm": _setting(
                settings, "DontTradeOnWeekends.FridayCloseTime"),
            "weekend_sunday_open_hhmm": _setting(
                settings, "DontTradeOnWeekends.SundayOpenTime"),
            "spread_in_sq": spread,
            "slippage_in_sq": _setting(settings, "Slippage"),
            **commission,
            "swap_enabled": _swap_enabled(settings, instrument),
            "point_value": point_value,
            "order_size_multiplier": order_size_multiplier,
            "tick_step": tick_step,
        },
        "entries": entries,
        "signal_variable_ids": sorted(signals),
        "entry_condition_counts": entry_condition_counts,
        "maximum_entry_conditions": max(entry_condition_counts.values()),
        "exit_signals": exit_signal_values,
        "supported": not unsupported,
        "unsupported_nodes_or_formulas": sorted(unsupported),
        "translation_status": "SUPPORTED_SUBSET" if not unsupported else "UNSUPPORTED",
    }
    return contract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqx", type=Path); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = extract(args.sqx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("strategy_name", "market", "translation_status",
                                                    "unsupported_nodes_or_formulas")}, indent=2))


if __name__ == "__main__": main()
