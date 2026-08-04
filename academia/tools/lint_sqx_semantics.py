#!/usr/bin/env python3
"""Detecta lògica degenerada i deriva de parts congelades en artifacts SQX."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


IGNORED_PARAMS = {"Identification", "Comment", "MagicNumber"}
SLPT_PARAMS = {"ProfitTarget.ProfitTarget", "StopLoss.StopLoss"}


def _strategy(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith("strategy_portfolio.xml")]
        if not members:
            raise KeyError("strategy_Portfolio.xml")
        return ET.fromstring(archive.read(members[0]))


def _children(item: ET.Element) -> list[ET.Element]:
    return [child for block in item.findall("./Block") for child in block.findall("./Item")]


def _constant(item: ET.Element) -> bool | None:
    key = item.get("key", "")
    if key == "Boolean":
        value = next((param.text or "" for param in item.findall("./Param") if param.get("key") == "#Value#"), None)
        if value is None:
            return None
        return value.strip().lower() == "true"
    children = _children(item)
    values = [_constant(child) for child in children]
    if key == "AND":
        if False in values:
            return False
        if values and all(value is True for value in values):
            return True
    if key == "OR":
        if True in values:
            return True
        if values and all(value is False for value in values):
            return False
    if key in {"NOT", "Negate"} and len(values) == 1 and values[0] is not None:
        return not values[0]
    return None


def _semantic_item(item: ET.Element, ignore_slpt: bool = False) -> tuple:
    params = []
    for param in item.findall("./Param"):
        key = (param.get("key") or "").strip("#")
        if key in IGNORED_PARAMS:
            continue
        if ignore_slpt and key in SLPT_PARAMS:
            continue
        formula = param.find("./Formula")
        value = (formula.get("key") if formula is not None else (param.text or "").strip())
        params.append((key, value))
    formulas = tuple(formula.get("key", "") for formula in item.findall("./Formula"))
    return item.get("key", ""), tuple(params), formulas, tuple(_semantic_item(child, ignore_slpt) for child in _children(item))


def _entry_contract(root: ET.Element, ignore_slpt: bool = False) -> dict:
    signals = {
        signal.get("variable", ""): _semantic_item(signal.find("./Item"))
        for signal in root.findall(".//signal") if signal.find("./Item") is not None
    }
    contract: dict[str, dict] = {}
    for rule in root.findall(".//Rule"):
        name = rule.get("name", "")
        if "entry" not in name.lower():
            continue
        variable = next(
            ((param.text or "").strip() for param in rule.findall("./If//Param") if param.get("key") == "#Variable#"),
            "",
        )
        orders = [_semantic_item(item, ignore_slpt) for item in rule.findall("./Then//Item") if item.get("key", "").startswith("Enter")]
        contract[name.lower()] = {"signal": signals.get(variable), "orders": orders}
    return contract


def _exit_signal_contract(root: ET.Element) -> dict:
    signals = {
        signal.get("variable", ""): _semantic_item(signal.find("./Item"))
        for signal in root.findall(".//signal") if signal.find("./Item") is not None
    }
    contract = {}
    for rule in root.findall(".//Rule"):
        name = rule.get("name", "")
        if "exit" not in name.lower():
            continue
        variable = next(
            ((param.text or "").strip() for param in rule.findall("./If//Param") if param.get("key") == "#Variable#"),
            "",
        )
        contract[name.lower()] = signals.get(variable)
    return contract


def _slpt_contract(root: ET.Element) -> dict:
    contract: dict[str, tuple] = {}
    for rule in root.findall(".//Rule"):
        name = rule.get("name", "")
        if "entry" not in name.lower():
            continue
        values = []
        for param in rule.findall("./Then//Param"):
            key = (param.get("key") or "").strip("#")
            if key not in SLPT_PARAMS:
                continue
            formula = param.find("./Formula")
            value = formula.get("key") if formula is not None else (param.text or "").strip()
            values.append((key, value))
        contract[name.lower()] = tuple(values)
    return contract


def lint(
    candidate: Path,
    base: Path | None = None,
    allow_entry_change: bool = False,
    allow_slpt_change: bool = False,
) -> dict:
    root = _strategy(candidate)
    findings = []
    for signal in root.findall(".//signal"):
        item = signal.find("./Item")
        if item is None:
            continue
        value = _constant(item)
        if value is not None:
            findings.append({
                "code": "CONSTANT_SIGNAL",
                "severity": "error",
                "variable": signal.get("variable"),
                "constant": value,
                "message": f"el senyal queda constant a {str(value).lower()}",
            })

    frozen_contract = None
    if base is not None:
        base_root = _strategy(base)
        base_contract = _entry_contract(base_root, allow_slpt_change)
        candidate_contract = _entry_contract(root, allow_slpt_change)
        entry_preserved = {
            name: value["signal"] for name, value in base_contract.items()
        } == {
            name: value["signal"] for name, value in candidate_contract.items()
        }
        orders_preserved = {
            name: value["orders"] for name, value in base_contract.items()
        } == {
            name: value["orders"] for name, value in candidate_contract.items()
        }
        exit_signals_preserved = _exit_signal_contract(base_root) == _exit_signal_contract(root)
        base_slpt = _slpt_contract(base_root)
        candidate_slpt = _slpt_contract(root)
        slpt_changed = base_slpt != candidate_slpt
        frozen_contract = {
            "entry_preserved": entry_preserved,
            "orders_preserved": orders_preserved,
            "exit_signals_preserved": exit_signals_preserved,
            "entry_change_allowed": allow_entry_change,
            "slpt_change_allowed": allow_slpt_change,
            "slpt_changed": slpt_changed,
            "base_slpt": base_slpt,
            "candidate_slpt": candidate_slpt,
            "entry_and_orders_preserved": entry_preserved and orders_preserved,
            "base_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        }
        if not orders_preserved or not exit_signals_preserved or (not allow_entry_change and not entry_preserved):
            findings.append({
                "code": "FROZEN_ENTRY_OR_ORDER_DRIFT",
                "severity": "error",
                "message": "ha canviat una part congelada de l'entrada o les ordres",
            })
        if allow_slpt_change and not slpt_changed:
            findings.append({
                "code": "EXPECTED_SLPT_CHANGE_MISSING",
                "severity": "error",
                "message": "s'ha demanat validar una millora SL/PT però els paràmetres SL/PT no han canviat",
            })

    errors = [finding for finding in findings if finding["severity"] == "error"]
    return {
        "passed": not errors,
        "candidate": str(candidate),
        "base": None if base is None else str(base),
        "frozen_contract": frozen_contract,
        "findings": findings,
        "interpretation": "Aquest lint detecta deriva estructural i constants; no prova robustesa ni rendibilitat.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--allow-entry-change", action="store_true")
    parser.add_argument("--allow-slpt-change", action="store_true")
    args = parser.parse_args()
    try:
        result = lint(args.candidate, args.base, args.allow_entry_change, args.allow_slpt_change)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        result = {"passed": False, "candidate": str(args.candidate), "findings": [{"code": "UNREADABLE_SQX", "severity": "error", "message": str(exc)}]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
