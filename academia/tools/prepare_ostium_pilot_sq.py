#!/usr/bin/env python3
"""Prepare three isolated SQ Builder projects for the non-comparative Ostium pilot."""

from __future__ import annotations

import argparse
import sqlite3
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


PROJECTS = {
    "EURUSD": {
        "project": "ACADEMIA_OSTIUM_PILOT_EURUSD_H4_ATR",
        "symbol": "EURUSD_M1_dukas_M1_UTCMinus05",
        "spread": "1.2",
        "slippage": "0.8",
    },
    "US500": {
        "project": "ACADEMIA_OSTIUM_PILOT_US500_H4_ATR",
        "symbol": "SP_M1_dukas",
        "spread": "1200",
        "slippage": "600",
    },
    "XAUUSD": {
        "project": "ACADEMIA_OSTIUM_PILOT_XAUUSD_H4_ATR",
        "symbol": "XAUUSD_M1_dukasXAUUSD_M1_dukas_NYclose",
        "spread": "1200",
        "slippage": "600",
    },
}
REQUIRED_ARCHITECTURE_TOKENS = ("EnterAtStop", "Highest", "Lowest", "ATR")


def instrument_element(row: sqlite3.Row) -> ET.Element:
    mapping = {
        "instrument": row["INSTRUMENT"], "description": row["DESCRIPTION"] or "",
        "tickSize": row["TICKSIZE"], "tickStep": row["TICKSTEP"],
        "minDistance": row["MIN_DISTANCE"], "tickValueInMoney": 0,
        "dateFrom": 0, "dateTo": 0, "rows": 0, "totalDays": 0,
        "defaultSpread": row["DEFAULTSPREAD"], "defaultSlippage": row["DEFAULTSLIPPAGE"],
        "decimals": max(0, len(str(row["TICKSTEP"]).split(".")[-1].rstrip("0"))),
        "commissions": row["COMMISSIONS"] or "", "pointValue": row["POINTVALUE"],
        "dataType": row["DATATYPE"], "recognizedFromOrders": "false",
        "exchange": row["EXCHANGE"] or "", "country": row["COUNTRY"] or "",
        "sector": row["SECTOR"] or "", "swap": row["SWAP"] or "",
        "orderSizeMultiplier": row["ORDERSIZEMULTIPLIER"],
        "orderSizeStep": row["ORDERSIZESTEP"], "broker": row["BROKER_ID"],
    }
    return ET.Element("InstrumentInfo", {key: str(value) for key, value in mapping.items()})


def catalog_symbol(db: sqlite3.Connection, name: str) -> ET.Element:
    db.row_factory = sqlite3.Row
    data = db.execute("SELECT * FROM DATA WHERE SYMBOL=?", (name,)).fetchone()
    if not data:
        raise ValueError(f"symbol absent from catalog: {name}")
    instrument = db.execute("SELECT * FROM INSTRUMENTS WHERE INSTRUMENT=?", (data["INSTRUMENT"],)).fetchone()
    if not instrument:
        raise ValueError(f"instrument absent from catalog: {data['INSTRUMENT']}")
    attrs = {
        "name": data["SYMBOL"], "source": data["SOURCE"], "barType": 1,
        "precision": data["TIMEFRAME"], "timezone": data["TIMEZONE"],
        "dateFrom": data["DATEFROM"], "dateTo": data["DATETO"],
        "uSymbol": data["USYMBOL"] or data["SYMBOL"],
        "uSymbolName": data["USYMBOLNAME"] or data["SYMBOL"],
        "removeWeekends": str(bool(data["REMOVE_WEEKENDS"])).lower(),
        "broker": data["BROKER_ID"],
    }
    element = ET.Element("Symbol", {key: str(value) for key, value in attrs.items()})
    element.append(instrument_element(instrument))
    return element


def find_symbol(root: ET.Element, name: str) -> ET.Element:
    matches = [item for item in root.findall(".//Symbols/Symbol") if item.get("name") == name]
    if not matches:
        raise ValueError(f"template symbol absent: {name}")
    return deepcopy(matches[0])


def add_drawdown_gate(root: ET.Element, maximum_drawdown_pct: float) -> None:
    conditions = root.find(".//Rankings/Conditions")
    if conditions is None:
        raise ValueError("missing ranking conditions")
    condition = ET.SubElement(conditions, "Condition", {"use": "true"})
    left = ET.SubElement(condition, "Left-Side", {"valueType": "column"})
    ET.SubElement(left, "Column-Value", {
        "column": "DrawdownPct", "columnType": "0", "name": "Max DD %",
        "format": "Decimal2Pct", "resultType": "main", "direction": "0",
        "sampleType": "127", "plType": "10", "confidenceLevel": "50",
        "market": "1", "subresult": "30", "pctRatio": "0", "class": "DrawdownPct",
    })
    ET.SubElement(condition, "Comparator", {"value": "<="})
    right = ET.SubElement(condition, "Right-Side", {"valueType": "numeric"})
    ET.SubElement(right, "Numeric-Value", {"value": str(maximum_drawdown_pct)})


def set_risk_sizing(root: ET.Element, risk_pct: float, maximum_drawdown_pct: float) -> None:
    methods = root.findall(".//RiskMoneyManagement/MoneyManagement/Method")
    risk_method = None
    for method in methods:
        method.set("use", "false")
        if method.get("type") == "RiskFixedBalancePct":
            risk_method = method
    if risk_method is None:
        raise ValueError("RiskFixedBalancePct money management unavailable")
    risk_method.set("use", "true")
    risk = risk_method.find(".//*[@key='Risk']")
    if risk is None:
        raise ValueError("RiskFixedBalancePct Risk parameter unavailable")
    risk.text = str(risk_pct)
    risk_management = root.find(".//RiskMoneyManagement/RiskManagement")
    if risk_management is None:
        raise ValueError("risk management unavailable")
    risk_management.set("maxDrawdown", str(maximum_drawdown_pct))
    add_drawdown_gate(root, maximum_drawdown_pct)


def rewrite(base_files: dict[str, bytes], project: dict, symbol: ET.Element,
            risk_pct: float | None = None, maximum_drawdown_pct: float = 15) -> dict[str, bytes]:
    files = dict(base_files)
    config = ET.fromstring(files["config.xml"])
    config.set("name", project["project"])
    files["config.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=True)

    root = ET.fromstring(files["Build-Task1.xml"])
    setups = root.findall(".//Setup")
    if len(setups) < 2:
        raise ValueError("expected main and dormant cross-check setups")
    for setup in setups:
        setup.set("dateFrom", "2017.01.01")
        setup.set("dateTo", "2021.12.31")
        setup.set("testPrecision", "2")
        setup.set("slippage", project["slippage"])
        for chart in setup.findall("Chart"):
            chart.set("symbol", project["symbol"])
            chart.set("timeframe", "H4")
            chart.set("spread", project["spread"])

    crosschecks = root.find(".//CrossChecks")
    if crosschecks is None or crosschecks.get("use") != "false":
        raise ValueError("pilot requires disabled cross-checks during cheap generation")
    stop = root.find(".//Rankings/StopCondition")
    if stop is None:
        raise ValueError("missing stop condition")
    stop.attrib.update({"type": "databank-full", "passedStrategies": "40", "restartCount": "0", "days": "0", "hours": "0", "minutes": "10"})
    if risk_pct is not None:
        set_risk_sizing(root, risk_pct, maximum_drawdown_pct)

    symbols = root.find(".//Resources/Symbols")
    instruments = root.find(".//Resources/Instruments")
    if symbols is None or instruments is None:
        raise ValueError("missing embedded SQ resources")
    symbols.clear()
    symbols.append(deepcopy(symbol))
    instruments.clear()
    instruments.append(deepcopy(symbol.find("InstrumentInfo")))

    referenced = {chart.get("symbol") for chart in root.findall(".//Setup/Chart")}
    embedded = {item.get("name") for item in root.findall(".//Resources/Symbols/Symbol")}
    if referenced != {project["symbol"]} or embedded != referenced:
        raise ValueError(f"unresolved symbol contract: referenced={referenced}, embedded={embedded}")
    rendered = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    missing_tokens = [token for token in REQUIRED_ARCHITECTURE_TOKENS if token.encode() not in rendered]
    if missing_tokens:
        raise ValueError(f"source does not enforce R2 architecture: missing {missing_tokens}")
    files["Build-Task1.xml"] = rendered
    return files


def prepare(base: Path, eur_template: Path, data_db: Path, output: Path,
            risk_pct: float | None = None, maximum_drawdown_pct: float = 15,
            project_suffix: str = "") -> list[Path]:
    with ZipFile(base) as archive:
        base_files = {name: archive.read(name) for name in archive.namelist()}
    with ZipFile(eur_template) as archive:
        eur_root = ET.fromstring(archive.read("Build-Task1.xml"))
    base_root = ET.fromstring(base_files["Build-Task1.xml"])
    with sqlite3.connect(f"file:{data_db}?mode=ro", uri=True) as db:
        symbols = {
            "EURUSD": find_symbol(eur_root, PROJECTS["EURUSD"]["symbol"]),
            "US500": catalog_symbol(db, PROJECTS["US500"]["symbol"]),
            "XAUUSD": find_symbol(base_root, PROJECTS["XAUUSD"]["symbol"]),
        }
    prepared = []
    for key, source_project in PROJECTS.items():
        project = dict(source_project)
        project["project"] += project_suffix
        target_dir = output / project["project"]
        if target_dir.exists():
            raise FileExistsError(f"refusing to overwrite prepared project: {target_dir}")
        prepared.append((target_dir, rewrite(
            base_files, project, symbols[key], risk_pct, maximum_drawdown_pct,
        )))
    created = []
    for target_dir, files in prepared:
        target_dir.mkdir(parents=True)
        target = target_dir / "project.cfx"
        with ZipFile(target, "w", ZIP_DEFLATED) as archive:
            for name, payload in files.items():
                archive.writestr(name, payload)
        created.append(target)
    return created


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--eur-template", type=Path, required=True)
    parser.add_argument("--data-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--risk-pct", type=float)
    parser.add_argument("--maximum-drawdown-pct", type=float, default=15)
    parser.add_argument("--project-suffix", default="")
    args = parser.parse_args()
    for path in prepare(
        args.base, args.eur_template, args.data_db, args.output,
        args.risk_pct, args.maximum_drawdown_pct, args.project_suffix,
    ):
        print(path)


if __name__ == "__main__":
    main()
