#!/usr/bin/env python3
"""Prepare an isolated BTC M15 MA/RSI pullback Builder project."""

from __future__ import annotations

import argparse
import sqlite3
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_ostium_pilot_sq import catalog_symbol, set_risk_sizing


PROJECT = "ACADEMIA_BTC_M15_TREND_PULLBACK_V1"
SIGNALS = {
    "MABarClosesAbove", "MABarClosesBelow", "MACrossUp", "MACrossDown",
    "RSILower", "RSIHigher", "RSICrossUp", "RSICrossDown",
}


def numeric_condition(parent: ET.Element, column: str, name: str, comparator: str, value: float) -> None:
    condition = ET.SubElement(parent, "Condition", {"use": "true"})
    left = ET.SubElement(condition, "Left-Side", {"valueType": "column"})
    ET.SubElement(left, "Column-Value", {
        "column": column, "columnType": "0", "name": name, "format": "Decimal2",
        "resultType": "main", "direction": "0", "sampleType": "127", "plType": "10",
        "confidenceLevel": "50", "market": "1", "subresult": "30", "pctRatio": "0", "class": column,
    })
    ET.SubElement(condition, "Comparator", {"value": comparator})
    right = ET.SubElement(condition, "Right-Side", {"valueType": "numeric"})
    ET.SubElement(right, "Numeric-Value", {"value": str(value)})


def prepare(template: Path, db_path: Path, output: Path) -> Path:
    with ZipFile(template) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    config = ET.fromstring(files["config.xml"])
    config.set("name", PROJECT)
    tasks = config.find("Tasks")
    if tasks is None:
        raise ValueError("missing project tasks")
    build_tasks = [task for task in tasks if task.get("type") == "Build"]
    if len(build_tasks) != 1:
        raise ValueError(f"expected exactly one Build task, found {len(build_tasks)}")
    tasks.clear()
    tasks.append(deepcopy(build_tasks[0]))
    files["config.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=True)
    files = {name: payload for name, payload in files.items() if name in {"config.xml", "Build-Task1.xml"}}
    root = ET.fromstring(files["Build-Task1.xml"])

    market_sides = root.find(".//MarketSides")
    complexity = root.find(".//RulesComplexity/Chart")
    strategy_type = root.find(".//StrategyType")
    if market_sides is None or complexity is None or strategy_type is None:
        raise ValueError("missing strategy architecture controls")
    market_sides.set("type", "both")
    strategy_type.set("additionalCharts", "0")
    complexity.attrib.update({"minConditions": "2", "maxConditions": "2", "minExitConditions": "0", "maxExitConditions": "0", "minPeriod": "5", "maxPeriod": "100"})

    for setup in root.findall(".//Setup"):
        setup.attrib.update({"dateFrom": "2019.10.01", "dateTo": "2021.12.31", "testPrecision": "2", "slippage": "5"})
        for chart in setup.findall("Chart"):
            chart.attrib.update({"symbol": "BTCUSDT", "timeframe": "M15", "spread": "5"})

    for block in root.findall(".//BuildingBlocks/Block"):
        if block.get("category") == "signals":
            block.set("use", "true" if block.get("key") in SIGNALS else "false")
    for block in root.findall(".//OrderTypes/Block"):
        block.set("use", "true" if block.get("key") == "EnterAtMarket" else "false")

    slpt = root.find(".//SLPTOptions")
    if slpt is None:
        raise ValueError("missing SLPT options")
    values = {
        "SLRequired": "true", "SLFixedPips": "false", "SLATR": "true",
        "MinSLATRMultiple": "1", "MaxSLATRMultiple": "3", "MinSLATRPeriod": "10", "MaxSLATRPeriod": "30",
        "PTRequired": "true", "PTFixedPips": "false", "PTATR": "true",
        "MinPTATRMultiple": "1", "MaxPTATRMultiple": "4", "MinPTATRPeriod": "10", "MaxPTATRPeriod": "30",
    }
    for key, value in values.items():
        item = slpt.find(key)
        if item is None:
            raise ValueError(f"missing SLPT field: {key}")
        item.text = value

    exit_after = root.find(".//ExitTypes/Block[@key='ExitAfterBars.ExitAfterBars']")
    if exit_after is not None:
        exit_after.set("use", "true")
        exit_after.set("probability", "100")
        parameter = exit_after.find(".//Param[@key='#ExitAfterBars#']")
        if parameter is not None:
            parameter.attrib.update({"minValue": "8", "maxValue": "32", "step": "4"})

    conditions = root.find(".//Rankings/Conditions")
    stop = root.find(".//Rankings/StopCondition")
    crosschecks = root.find(".//CrossChecks")
    if conditions is None or stop is None or crosschecks is None:
        raise ValueError("missing ranking or crosscheck controls")
    conditions.clear()
    numeric_condition(conditions, "ProfitFactor", "Profit factor", ">", 1.1)
    numeric_condition(conditions, "NumberOfTrades", "Number of trades", ">=", 150)
    numeric_condition(conditions, "ReturnDDRatio", "Return/DD", ">", 1.0)
    stop.attrib.update({"type": "databank-full", "passedStrategies": "20", "restartCount": "0", "days": "0", "hours": "0", "minutes": "10"})
    crosschecks.set("use", "false")
    set_risk_sizing(root, 1.0, 15)

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
        symbol = catalog_symbol(db, "BTCUSDT")
    symbol.attrib.update({"broker": "12", "uSymbol": "BTCUSD", "uSymbolName": "BTCUSD"})
    instrument = symbol.find("InstrumentInfo")
    if instrument is None:
        raise ValueError("BTC symbol lacks embedded instrument")
    instrument.attrib.update({
        "instrument": "BTCUSDOST", "description": "BTCUSDT discovery data mapped to Ostium BTC/USD",
        "broker": "12", "dataType": "3", "orderSizeMultiplier": "1.0", "orderSizeStep": "0.001",
        "defaultSpread": "5", "defaultSlippage": "5",
    })
    resources_symbols = root.find(".//Resources/Symbols")
    resources_instruments = root.find(".//Resources/Instruments")
    if resources_symbols is None or resources_instruments is None:
        raise ValueError("missing embedded resources")
    resources_symbols.clear()
    resources_symbols.append(deepcopy(symbol))
    resources_instruments.clear()
    resources_instruments.append(deepcopy(instrument))

    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    for token in (b"BTCUSDT", b"BTCUSDOST", b"M15", b"MABarClosesAbove", b"RSILower", b"EnterAtMarket"):
        if token not in rendered:
            raise ValueError(f"missing contract token: {token.decode()}")
    files["Build-Task1.xml"] = rendered
    target = output / PROJECT / "project.cfx"
    if target.exists():
        raise FileExistsError(f"refusing to overwrite: {target}")
    target.parent.mkdir(parents=True)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--data-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.template, args.data_db, args.output))


if __name__ == "__main__":
    main()
