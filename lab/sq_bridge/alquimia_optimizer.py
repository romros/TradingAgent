#!/usr/bin/env python3
"""Generate a sealed-train SQ Optimizer CFX for a fixed Alquimia seed."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.alquimia_retest import _condition, _graft_resource_symbol


def _read_member(path: Path, member: str) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read(member))


def generate(scaffold: Path, output: Path, project_name: str, family_path: Path,
             seed: Path, resource_source: Path, symbol: str, timeframe: str,
             *, task_file: str = "Optimize-Task1.xml",
             resource_task_file: str = "Build-Task1.xml",
             max_optimizations: int = 5000, max_steps: int = 5,
             slippage: float = 400, test_precision: int = 2) -> dict:
    family = json.loads(family_path.read_text(encoding="utf-8"))
    if family.get("legacy_quantitative_inputs") != []:
        raise ValueError("LEGACY_QUANTITATIVE_INPUTS_FORBIDDEN")
    if family.get("holdout_release_authorized") is not False:
        raise ValueError("HOLDOUT_MUST_REMAIN_SEALED")
    if not 1 <= max_steps <= 20 or not 1 <= max_optimizations <= 5000:
        raise ValueError("OPTIMIZATION_BUDGET_INVALID")
    task = _read_member(scaffold, task_file)
    resource = _read_member(resource_source, resource_task_file)
    _graft_resource_symbol(task, resource, symbol)

    setup = task.find("./Data/Setups/Setup")
    if setup is None:
        raise ValueError("OPTIMIZER_SETUP_MISSING")
    setup.set("dateFrom", family["periods"]["train_from"].replace("-", "."))
    setup.set("dateTo", family["periods"]["train_to"].replace("-", "."))
    setup.set("testPrecision", str(test_precision))
    setup.set("slippage", str(slippage))
    charts = setup.findall("./Chart")
    if not charts:
        raise ValueError("OPTIMIZER_CHART_MISSING")
    for extra in charts[1:]:
        setup.remove(extra)
    charts[0].set("symbol", symbol)
    charts[0].set("timeframe", timeframe)
    charts[0].set("spread", "0")
    oos = task.find("./Data/OutOfSample")
    if oos is None:
        raise ValueError("OUT_OF_SAMPLE_NODE_MISSING")
    oos.clear(); oos.set("showGraph", "false")

    commissions = setup.findall("./Commissions/Method")
    none = next((node for node in commissions if node.get("type") == "None"), None)
    if none is None:
        raise ValueError("COMMISSION_NONE_MISSING")
    for method in commissions:
        method.set("use", "true" if method is none else "false")
    money = task.find("./RiskMoneyManagement/MoneyManagement")
    if money is None:
        raise ValueError("MONEY_MANAGEMENT_MISSING")
    fixed = money.find("./Method[@type='FixedSize']")
    if fixed is None:
        raise ValueError("FIXED_SIZE_MISSING")
    for method in money.findall("./Method"):
        method.set("use", "true" if method is fixed else "false")
    size = fixed.find("./Params/Param[@key='Size']")
    if size is None:
        raise ValueError("FIXED_SIZE_PARAMETER_MISSING")
    size.text = "0.01"
    money.find("./InitialCapital").text = "10000"

    optimization = task.find("./Optimization")
    if optimization is None:
        raise ValueError("OPTIMIZATION_NODE_MISSING")
    optimization.set("maxOptimizations", str(max_optimizations))
    source = optimization.find("./Source")
    source.set("type", "1"); source.set("relativePath", "false")
    source.text = str(seed)
    simple = optimization.find("./SimpleOptimization")
    simple.set("resultsCount", "200"); simple.set("stabilityRange", "20")
    method = optimization.find("./OptimizationMethod")
    method.attrib.update({"settings": "automatic", "symmetricVariables": "true",
                          "symmetryDisabled": "false", "method": "brute-force",
                          "maxSteps": str(max_steps)})
    manual = optimization.find("./ManualSettings/Params")
    if manual is not None:
        manual.clear()
    what = optimization.find("./WhatToParametrize")
    choices = {
        "Recommended": False, "Periods": True, "Shifts": False,
        "Constants": False, "OtherParams": True, "EntryParams": True,
        "EntryLogic": False, "ExitParamsUsed": True,
        "ExitParamsUnused": False, "BooleanParams": False,
        "TradingOptions": False,
    }
    for key, enabled in choices.items():
        node = what.find(f"./{key}")
        if node is not None:
            node.text = str(enabled).lower()
    automatic = optimization.find("./AutomaticSettings")
    automatic.set("distribution", "20"); automatic.set("maxSteps", str(max_steps))

    rankings = task.find("./Rankings")
    rankings.set("type", "never")
    rankings.find("./MaxStrategies").text = "200"
    ranking = rankings.find("./FitnessCriteria/Settings/Ranking")
    ranking.set("type", "ReturnDDRatio")
    conditions = rankings.find("./Conditions")
    conditions.clear()
    conditions.extend([
        _condition("NumberOfTrades", "Integer", ">=", family["pre_registered_falsifiers"]["minimum_discovery_trades"]),
        _condition("ProfitFactor", "Decimal2", ">=", family["pre_registered_falsifiers"]["minimum_discovery_profit_factor"]),
    ])
    rankings.find("./StopCondition").attrib.update(
        {"type": "never", "passedStrategies": "1000", "days": "0", "hours": "0", "minutes": "0"}
    )
    task.find("./Databanks/Databank[@name='Input']").set("value", "Strategies to optimize")
    task.find("./Databanks/Databank[@name='Output']").set("value", "Results")

    config = ET.Element("Project", {"name": project_name, "version": "143.2708"})
    tasks = ET.SubElement(config, "Tasks")
    ET.SubElement(tasks, "Task", {"type": "Optimize", "name": "fixed seed optimize",
        "active": "true", "taskXMLFile": task_file})
    databanks = ET.SubElement(config, "Databanks")
    for position, name in enumerate(("Results", "Strategies to optimize")):
        ET.SubElement(databanks, "Databank", {"name": name,
            "view": "Default - Main data - Full sample",
            "syncType": "Auto-sync every 10 minutes", "position": str(position)})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("config.xml", ET.tostring(config, encoding="utf-8"))
        archive.writestr(task_file, ET.tostring(task, encoding="utf-8"))
    result = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "hypothesis_id": family["hypothesis_id"],
        "stage": "discovery_parameter_search",
        "date_from": family["periods"]["train_from"],
        "date_to": family["periods"]["train_to"],
        "holdout_accessed": False,
        "holdout_release_authorized": False,
        "entry_logic_mutation": False,
        "legacy_quantitative_inputs": [],
        "max_optimizations": max_optimizations,
        "max_steps_per_parameter": max_steps,
        "seed": str(seed),
        "seed_sha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
        "family_sha256": hashlib.sha256(family_path.read_bytes()).hexdigest(),
        "scaffold_role": "optimizer_xml_syntax_only",
        "scaffold_sha256": hashlib.sha256(scaffold.read_bytes()).hexdigest(),
        "resource_source_sha256": hashlib.sha256(resource_source.read_bytes()).hexdigest(),
        "symbol": symbol, "timeframe": timeframe,
        "slippage": slippage, "test_precision": test_precision,
        "cfx_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scaffold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--family", type=Path, required=True)
    parser.add_argument("--seed", type=Path, required=True,
                        help="Ruta de la llavor tal com serà visible dins SQCLI")
    parser.add_argument("--seed-hash-source", type=Path,
                        help="Fitxer local equivalent quan --seed és una ruta del contenidor")
    parser.add_argument("--resource-source", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--max-optimizations", type=int, default=5000)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--slippage", type=float, default=400)
    parser.add_argument("--test-precision", type=int, default=2)
    args = parser.parse_args()
    hash_source = args.seed_hash_source or args.seed
    result = generate(args.scaffold, args.output, args.name, args.family,
        hash_source, args.resource_source, args.symbol, args.timeframe,
        max_optimizations=args.max_optimizations, max_steps=args.max_steps,
        slippage=args.slippage, test_precision=args.test_precision)
    # The task must reference the container-visible path, while the manifest hashes
    # the local byte-identical source.
    if args.seed_hash_source:
        with zipfile.ZipFile(args.output, "r") as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        task = ET.fromstring(members["Optimize-Task1.xml"])
        task.find("./Optimization/Source").text = str(args.seed)
        members["Optimize-Task1.xml"] = ET.tostring(task, encoding="utf-8")
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in members.items(): archive.writestr(name, raw)
        result["seed"] = str(args.seed)
        result["cfx_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
        args.output.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
