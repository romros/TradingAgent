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


def _semantic_item(item: ET.Element) -> tuple:
    params = []
    for param in item.findall("./Param"):
        key = (param.get("key") or "").strip("#")
        if key in IGNORED_PARAMS:
            continue
        formula = param.find("./Formula")
        value = (formula.get("key") if formula is not None else (param.text or "").strip())
        params.append((key, value))
    formulas = tuple(formula.get("key", "") for formula in item.findall("./Formula"))
    return item.get("key", ""), tuple(params), formulas, tuple(_semantic_item(child) for child in _children(item))


def _entry_contract(root: ET.Element) -> dict:
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
        orders = [_semantic_item(item) for item in rule.findall("./Then//Item") if item.get("key", "").startswith("Enter")]
        contract[name.lower()] = {"signal": signals.get(variable), "orders": orders}
    return contract


def lint(candidate: Path, base: Path | None = None) -> dict:
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
        base_contract = _entry_contract(_strategy(base))
        candidate_contract = _entry_contract(root)
        frozen_contract = {
            "entry_and_orders_preserved": base_contract == candidate_contract,
            "base_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        }
        if base_contract != candidate_contract:
            findings.append({
                "code": "FROZEN_ENTRY_OR_ORDER_DRIFT",
                "severity": "error",
                "message": "l'entrada o les ordres han canviat respecte de la base",
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
    args = parser.parse_args()
    try:
        result = lint(args.candidate, args.base)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        result = {"passed": False, "candidate": str(args.candidate), "findings": [{"code": "UNREADABLE_SQX", "severity": "error", "message": str(exc)}]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
