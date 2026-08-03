#!/usr/bin/env python3
"""Build a native fixed-shape sweep/reclaim SQX from an SQX syntax scaffold."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


def _prototype(root: ET.Element, key: str) -> ET.Element:
    node = root.find(f".//Item[@key='{key}']")
    if node is None:
        raise ValueError(f"SQX_SCAFFOLD_MISSING_ITEM:{key}")
    return copy.deepcopy(node)


def _fixed(node: ET.Element) -> ET.Element:
    for element in node.iter():
        for key in ("gid", "generated", "randomId", "retries"):
            element.attrib.pop(key, None)
    return node


def _param(node: ET.Element, key: str, value: int | float | str) -> None:
    param = node.find(f"./Param[@key='{key}']")
    if param is None:
        raise ValueError(f"SQX_SCAFFOLD_MISSING_PARAM:{node.get('key')}:{key}")
    param.text = str(value)


def _operand(root: ET.Element, key: str, *, computed_from: int | None = None,
             period: int | None = None, shift: int) -> ET.Element:
    node = _prototype(root, key)
    _param(node, "#Shift#", shift)
    if computed_from is not None:
        _param(node, "#ComputedFrom#", computed_from)
    if period is not None:
        _param(node, "#Period#", period)
        period_node = node.find("./Param[@key='#Period#']")
        period_node.attrib.update({"minValue": "5", "maxValue": "60",
                                   "builderMinValue": "5", "builderMaxValue": "60",
                                   "step": "1", "builderStep": "1"})
    return node


def _comparison(root: ET.Element, key: str, left: ET.Element,
                right: ET.Element) -> ET.Element:
    node = _prototype(root, key)
    for child in list(node):
        if child.tag in {"Block", "Item"}:
            node.remove(child)
    for block_key, operand in (("#Left#", left), ("#Right#", right)):
        block = ET.SubElement(node, "Block", {"key": block_key})
        block.append(operand)
    return node


def _and(root: ET.Element, *conditions: ET.Element) -> ET.Element:
    node = _prototype(root, "AND")
    for child in list(node):
        if child.tag in {"Block", "Item"}:
            node.remove(child)
    for condition in conditions:
        node.append(condition)
    return node


def _signal(root: ET.Element, direction: str, lookback: int) -> ET.Element:
    if direction == "long":
        threshold_key, extreme_key, computed_from = "Lowest", "Low", 3
        break_key, reclaim_key = "IsLower", "IsGreater"
    elif direction == "short":
        threshold_key, extreme_key, computed_from = "Highest", "High", 2
        break_key, reclaim_key = "IsGreater", "IsLower"
    else:
        raise ValueError(f"INVALID_DIRECTION:{direction}")
    threshold_a = _operand(root, threshold_key, computed_from=computed_from,
                           period=lookback, shift=2)
    threshold_b = copy.deepcopy(threshold_a)
    break_condition = _comparison(
        root, break_key, _operand(root, extreme_key, shift=1), threshold_a
    )
    reclaim_condition = _comparison(
        root, reclaim_key, _operand(root, "Close", shift=1), threshold_b
    )
    return _fixed(_and(root, break_condition, reclaim_condition))


def _entry_signal(root: ET.Element, rule_name: str) -> ET.Element:
    rule = root.find(f".//Rule[@name='{rule_name}']")
    if rule is None:
        raise ValueError(f"SQX_SCAFFOLD_MISSING_RULE:{rule_name}")
    variable = rule.find(".//If//Param[@key='#Variable#']")
    if variable is None or not (variable.text or "").strip():
        raise ValueError(f"SQX_SCAFFOLD_MISSING_VARIABLE:{rule_name}")
    signal = root.find(f".//Rule[@type='Signal']/signals/signal[@variable='{variable.text.strip()}']")
    if signal is None:
        raise ValueError(f"SQX_SCAFFOLD_MISSING_SIGNAL:{rule_name}")
    return signal


def _replace_signal(signal: ET.Element, item: ET.Element) -> None:
    for child in list(signal):
        signal.remove(child)
    signal.append(item)


def _set_entry_exits(root: ET.Element, exit_after_bars: int, atr_period: int,
                     stop_atr: float, target_atr: float) -> None:
    for rule_name in ("Long entry", "Short entry"):
        action = root.find(f".//Rule[@name='{rule_name}']/Then/Item[@key='EnterAtMarket']")
        if action is None:
            raise ValueError(f"SQX_SCAFFOLD_ENTRY_NOT_MARKET:{rule_name}")
        _param(action, "#ExitAfterBars.ExitAfterBars#", exit_after_bars)
        exit_bars = action.find("./Param[@key='#ExitAfterBars.ExitAfterBars#']")
        exit_bars.attrib.update({"minValue": "2", "maxValue": "12",
                                 "builderMinValue": "2", "builderMaxValue": "12",
                                 "step": "1", "builderStep": "1"})
        for key, multiple in (
            ("#StopLoss.StopLoss#", stop_atr),
            ("#ProfitTarget.ProfitTarget#", target_atr),
        ):
            formula = action.find(f"./Param[@key='{key}']/Formula")
            if formula is None or formula.get("key") != "SQ.Formulas.SLPT.ATRBasedValue":
                raise ValueError(f"SQX_SCAFFOLD_ATR_EXIT_REQUIRED:{rule_name}:{key}")
            _param(formula, "#Value#", multiple)
            _param(formula, "#AtrPeriod#", atr_period)
            value = formula.find("./Param[@key='#Value#']")
            value.attrib.update({"minValue": "1", "maxValue": "4",
                                 "builderMinValue": "1", "builderMaxValue": "4",
                                 "step": "0.5", "builderStep": "0.5"})
            period = formula.find("./Param[@key='#AtrPeriod#']")
            period.attrib.update({"minValue": "10", "maxValue": "30",
                                  "builderMinValue": "10", "builderMaxValue": "30",
                                  "step": "2", "builderStep": "2"})


def _clean_settings(raw: bytes, name: str) -> bytes:
    root = ET.fromstring(raw)
    root.set("ResultName", name)
    for node in root.findall(".//StrategyName"):
        node.text = name
    for fitnesses in root.findall(".//Fitnesses"):
        for key in fitnesses.attrib:
            fitnesses.set(key, "0.0")
    for values in root.findall(".//Result/ValuesMap"):
        for child in list(values):
            if child.tag.startswith("stats_"):
                values.remove(child)
    for settings in root.findall(".//SpecialValuesMap/SettingsMap"):
        for child in list(settings):
            settings.remove(child)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rename_settings(raw: bytes, name: str) -> bytes:
    root = ET.fromstring(raw)
    root.set("ResultName", name)
    for node in root.findall(".//StrategyName"):
        node.text = name
    for fingerprint in root.findall(".//Fingerprint"):
        fingerprint.set("strategyName", name)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_seed(source: Path, output: Path, *, name: str, lookback: int = 20,
               exit_after_bars: int = 6, atr_period: int = 14,
               stop_atr: float = 2.0, target_atr: float = 2.0,
               loader_compatibility: bool = False) -> dict:
    with zipfile.ZipFile(source) as archive:
        members = {member: archive.read(member) for member in archive.namelist()}
    required = {"strategy_Portfolio.xml", "settings.xml", "lastSettings.xml", "version.txt"}
    missing = sorted(required - members.keys())
    if missing:
        raise ValueError(f"SQX_SCAFFOLD_MISSING_MEMBERS:{missing}")
    root = ET.fromstring(members["strategy_Portfolio.xml"])
    _replace_signal(_entry_signal(root, "Long entry"), _signal(root, "long", lookback))
    _replace_signal(_entry_signal(root, "Short entry"), _signal(root, "short", lookback))
    _set_entry_exits(root, exit_after_bars, atr_period, stop_atr, target_atr)
    strategy = root.find("./Strategy")
    if strategy is not None:
        strategy.set("name", name)
    strategy_name = root.find("./options/StrategyName")
    if strategy_name is not None:
        strategy_name.text = name
    strategy_raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    # Quantitative results from the syntax scaffold are deliberately discarded.
    retained = dict(members) if loader_compatibility else {
        key: value for key, value in members.items()
        if not key.startswith("Results/") and key != "orders.bin"
    }
    retained["strategy_Portfolio.xml"] = strategy_raw
    retained["settings.xml"] = (
        _rename_settings(retained["settings.xml"], name) if loader_compatibility
        else _clean_settings(retained["settings.xml"], name)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in sorted(retained):
            archive.writestr(key, retained[key])
    result = {
        "schema_version": 1,
        "strategy_name": name,
        "hypothesis": "xau-h4-sweep-reclaim-v5-fixed-seed",
        "source_role": "sqx_syntax_scaffold_only",
        "source_quantitative_results_retained": loader_compatibility,
        "source_quantitative_results_role": (
            "loader_compatibility_only_never_evidence" if loader_compatibility else "discarded"
        ),
        "lookback": lookback,
        "signal_bar_shift": 1,
        "prior_range_shift": 2,
        "exit_after_bars": exit_after_bars,
        "atr_period": atr_period,
        "stop_atr": stop_atr,
        "target_atr": target_atr,
        "optimizer_bounds": {
            "lookback": [5, 60], "exit_after_bars": [2, 12],
            "atr_period": [10, 30], "stop_atr": [1, 4], "target_atr": [1, 4]
        },
        "sqx_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "strategy_xml_sha256": hashlib.sha256(strategy_raw).hexdigest(),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--name", default="ALQUIMIA_XAU_H4_SWEEP_RECLAIM_V5_SEED")
    parser.add_argument("--lookback", type=int, default=20)
    parser.add_argument("--loader-compatibility", action="store_true",
                        help="Reté payload quantitatiu només perquè Retester regeneri un SQX fresc")
    args = parser.parse_args()
    result = build_seed(args.source, args.output, name=args.name, lookback=args.lookback,
                        loader_compatibility=args.loader_compatibility)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
