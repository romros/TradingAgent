#!/usr/bin/env python3
"""Compara semanticament un CFX generat amb el round-trip desat per SQ."""
from __future__ import annotations
import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def _read(path: Path) -> tuple[ET.Element, ET.Element]:
    with zipfile.ZipFile(path) as archive:
        config = ET.fromstring(archive.read("config.xml"))
        task = config.find("./Tasks/Task[@type='Build']")
        if task is None:
            raise ValueError(f"Build task absent a {path}")
        return config, ET.fromstring(archive.read(task.get("taskXMLFile")))

def _active_blocks(root: ET.Element) -> set[str]:
    return {node.get("key") for node in root.findall(".//Block") if node.get("use") == "true"}

def _snapshot(config: ET.Element, build: ET.Element) -> dict:
    setup = build.find("./Data/Setups/Setup")
    ranking_conditions = []
    for condition in build.findall("./Rankings/Conditions/Condition"):
        ranking_conditions.append({
            "column": condition.find("./Left-Side/Column-Value").get("column"),
            "comparator": condition.find("Comparator").get("value"),
            "value": condition.find("./Right-Side/Numeric-Value").get("value"),
            "use": condition.get("use"),
        })
    return {
        "project": config.get("name"),
        "tasks": [(node.get("type"), node.get("name")) for node in config.findall("./Tasks/Task")],
        "strategy_type": build.find("./WhatToBuild/StrategyType").get("type"),
        "market_sides": build.find("./WhatToBuild/MarketSides").get("type"),
        "population": build.findtext("./WhatToBuild/BuildMode/PopulationSize"),
        "islands": build.findtext("./WhatToBuild/BuildMode/Islands"),
        "initial_capital": build.findtext("./RiskMoneyManagement/MoneyManagement/InitialCapital"),
        "date_from": setup.get("dateFrom"), "date_to": setup.get("dateTo"),
        "symbol": setup.find("Chart").get("symbol"), "timeframe": setup.find("Chart").get("timeframe"),
        "max_strategies": build.findtext("./Rankings/MaxStrategies"),
        "ranking_conditions": ranking_conditions,
        "crosschecks": build.find("./CrossChecks").get("use"),
        "active_blocks": sorted(_active_blocks(build)),
    }

def compare(generated: Path, roundtrip: Path) -> dict:
    before = _snapshot(*_read(generated)); after = _snapshot(*_read(roundtrip))
    differences = {key: {"generated": before[key], "roundtrip": after[key]}
                   for key in before if before[key] != after[key]}
    return {"passed": not differences, "differences": differences, "snapshot": after}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated", type=Path); parser.add_argument("roundtrip", type=Path)
    args = parser.parse_args(); result = compare(args.generated, args.roundtrip)
    print(json.dumps(result, indent=2)); raise SystemExit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()
