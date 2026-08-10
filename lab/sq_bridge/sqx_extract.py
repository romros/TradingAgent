#!/usr/bin/env python3
"""Extreu un contracte JSON reproduible d'un SQX limitat al subset Alquimia."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SUPPORTED_SIGNAL_NODES = {
    "AND", "IsRising", "IsFalling", "CrossesAbove", "CrossesBelow",
    "IsGreater", "IsLower", "Close", "Low", "High", "SMA", "EMA", "RSI",
    "ROC", "Highest", "Lowest", "BarDayOfMonth", "BarDayOfWeekIs", "IsMonthFirstTradingDay",
    "IsMonthLastTradingDay", "ADX", "Number", "Boolean",
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


def _setting(root: ET.Element, key: str):
    node = root.find(f".//*[@key='{key}']")
    if node is None:
        node = root.find(f".//{key}")
    return _value(node) if node is not None else None


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
        variable = rule.find(".//If//Param[@key='#Variable#']")
        action = rule.find("./Then/Item")
        # Els projectes directionals de SQ conserven la regla oposada amb Then buit.
        if action is None:
            entries[direction] = None
            continue
        if variable is None: raise ValueError(f"{rule_name} no interpretable")
        signal_id = str(_value(variable))
        if signal_id not in signals:
            raise ValueError(f"{rule_name} referencia un signal inexistent: {signal_id}")
        signal = signals[signal_id]
        unsupported.update(_ops(signal) - SUPPORTED_SIGNAL_NODES)
        if any(node["op"] in {"SMA", "EMA", "RSI"}
               and node.get("params", {}).get("#ComputedFrom#", 0) != 0
               for node in _nodes(signal)):
            unsupported.add("NON_CLOSE_COMPUTED_FROM")
        if action.attrib["key"] not in SUPPORTED_ENTRY: unsupported.add(action.attrib["key"])
        action_ast = _item(action)
        for formula in action.findall(".//Formula"):
            formulas.add(formula.attrib["key"])
        entries[direction] = {
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
    contract = {
        "schema_version": 1,
        "source": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "strategy_xml_sha256": hashlib.sha256(strategy_raw).hexdigest(),
        "strategy_name": _setting(settings, "StrategyName"),
        "market": {"symbol": _setting(settings, "Symbol"), "timeframe": _setting(settings, "Timeframe")},
        "execution": {
            "exit_at_end_of_day": _setting(settings, "ExitAtEndOfDay.ExitAtEndOfDay"),
            "eod_exit_time_hhmm": _setting(settings, "ExitAtEndOfDay.EODExitTime"),
            "slippage_in_sq": _setting(settings, "Slippage"),
            "swap_enabled": False,
        },
        "entries": entries,
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
