#!/usr/bin/env python3
"""Genera un CFX Retest per una etapa temporal segellada d'Alquimia."""
from __future__ import annotations
import argparse
import hashlib
import json
import copy
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.methodology import validate

PERIOD_KEYS = {"train": ("train_from", "train_to"),
               "validation": ("validation_from", "validation_to"),
               "oos": ("oos_from", "oos_to"), "holdout": ("holdout_from", "holdout_to")}

def _require_resource_symbol(task_xml: ET.Element, symbol: str) -> None:
    resource_symbols = task_xml.findall("./Resources/Symbols/Symbol")
    matching = [node for node in resource_symbols if node.get("name") == symbol]
    if len(matching) != 1:
        available = sorted(node.get("name", "") for node in resource_symbols)
        raise ValueError(
            f"RESOURCE_SYMBOL_MISMATCH: {symbol!r} no te exactament un recurs; "
            f"disponibles={available}"
        )

def _read_task(archive_path: Path, task_file: str) -> ET.Element:
    with zipfile.ZipFile(archive_path) as archive:
        return ET.fromstring(archive.read(task_file))

def _graft_resource_symbol(task_xml: ET.Element, resource_xml: ET.Element, symbol: str) -> None:
    """Replace the target task's symbol resources with one exact, verified resource."""
    _require_resource_symbol(resource_xml, symbol)
    target = task_xml.find("./Resources/Symbols")
    source = resource_xml.find(f"./Resources/Symbols/Symbol[@name='{symbol}']")
    if target is None or source is None:
        raise ValueError("RESOURCE_SYMBOL_CONTAINER_MISSING")
    target.clear()
    target.append(copy.deepcopy(source))
    _require_resource_symbol(task_xml, symbol)

def _select_all_input_strategies(task_xml: ET.Element) -> None:
    databanks = task_xml.find("./Databanks")
    if databanks is None:
        raise ValueError("DATABANKS_NODE_MISSING")
    databanks.set("retestSelected", "false")
    selected = task_xml.find("./SelectedStrategies")
    if selected is None:
        selected = ET.SubElement(task_xml, "SelectedStrategies")
    selected.clear()

def _condition(column: str, fmt: str, comparator: str, threshold: float) -> ET.Element:
    node = ET.Element("Condition", {"use": "true"})
    left = ET.SubElement(node, "Left-Side", {"valueType": "column"})
    ET.SubElement(left, "Column-Value", {"column": column, "columnType": "0", "format": fmt,
        "resultType": "main", "direction": "0", "sampleType": "127", "plType": "10",
        "confidenceLevel": "50", "market": "1", "subresult": "30", "pctRatio": "0", "class": column})
    ET.SubElement(node, "Comparator", {"value": comparator})
    right = ET.SubElement(node, "Right-Side", {"valueType": "numeric"})
    ET.SubElement(right, "Numeric-Value", {"value": str(threshold)})
    return node

def generate(source: Path, output: Path, project_name: str, stage: str, manifest_path: Path,
             methodology_path: Path, symbol: str, timeframe: str,
             source_task_file: str = "Retest-Task1.xml", resource_source: Path | None = None,
             resource_task_file: str = "Build-Task1.xml", slippage: float = 0,
             test_precision: int = 4, money_management: str = "risk_percent",
             fixed_size: float = 1, keep_failed: bool = False) -> dict:
    if stage not in PERIOD_KEYS:
        raise ValueError(f"Etapa invalida: {stage}")
    methodology = json.loads(methodology_path.read_text())
    errors = validate(methodology)
    if errors:
        raise ValueError("Metodologia invalida: " + "; ".join(errors))
    discovery = json.loads(manifest_path.read_text())
    periods = discovery.get("periods")
    required_periods = {key for pair in PERIOD_KEYS.values() for key in pair}
    if not isinstance(periods, dict) or not required_periods.issubset(periods):
        missing = sorted(required_periods - set(periods or {}))
        raise ValueError(f"DISCOVERY_PERIODS_MISSING: {missing}")
    if stage == "holdout" and not discovery.get("holdout_release_authorized", False):
        raise ValueError("HOLDOUT_LOCKED: cal autoritzacio explicita al manifest")
    start_key, end_key = PERIOD_KEYS[stage]
    task_xml = _read_task(source, source_task_file)
    if resource_source is not None:
        _graft_resource_symbol(task_xml, _read_task(resource_source, resource_task_file), symbol)
    setup = task_xml.find("./Data/Setups/Setup")
    setup.set("dateFrom", periods[start_key].replace("-", "."))
    setup.set("dateTo", periods[end_key].replace("-", "."))
    if test_precision not in {1, 2, 3, 4}:
        raise ValueError("TEST_PRECISION_INVALID")
    setup.set("testPrecision", str(test_precision))
    out_of_sample = task_xml.find("./Data/OutOfSample")
    if out_of_sample is None:
        raise ValueError("OUT_OF_SAMPLE_NODE_MISSING")
    out_of_sample.clear()
    out_of_sample.set("showGraph", "false")
    charts = setup.findall("Chart")
    for extra in charts[1:]: setup.remove(extra)
    if not symbol or not timeframe:
        raise ValueError("symbol i timeframe son obligatoris")
    charts[0].set("symbol", symbol)
    charts[0].set("timeframe", timeframe); charts[0].set("spread", "0")
    if slippage < 0:
        raise ValueError("SLIPPAGE_NEGATIVE")
    setup.set("slippage", str(slippage))
    _require_resource_symbol(task_xml, symbol)
    commission_methods = setup.findall("./Commissions/Method")
    if not commission_methods:
        raise ValueError("COMMISSION_METHOD_MISSING")
    chosen_commission = next((m for m in commission_methods if m.get("type") == "None"),
                             commission_methods[0])
    for method in commission_methods:
        method.set("use", "true" if method is chosen_commission else "false")
    if chosen_commission.get("type") != "None":
        for param in chosen_commission.findall("./Params/Param"):
            if param.get("key") == "Commission":
                param.text = "0"
    money_methods = task_xml.findall("./RiskMoneyManagement/MoneyManagement/Method")
    method_type = {"risk_percent": "RiskFixedPctOfAccount", "fixed_size": "FixedSize"}.get(money_management)
    if method_type is None:
        raise ValueError("MONEY_MANAGEMENT_INVALID")
    selected_method = next((m for m in money_methods if m.get("type") == method_type), None)
    if selected_method is None:
        raise ValueError(f"MONEY_MANAGEMENT_MISSING: {method_type}")
    for method in money_methods:
        method.set("use", "true" if method is selected_method else "false")
    if money_management == "risk_percent":
        risk_parameter = selected_method.find("./Parameter[@key='Risk']")
        if risk_parameter is None:
            raise ValueError("RISK_PERCENT_PARAMETER_MISSING")
        risk_parameter.text = str(methodology["small_account"]["maximum_risk_per_trade_pct"])
        for key, value in (("Decimals", "3"), ("LotsIfNoMM", "0.001"), ("MaxLots", "100")):
            parameter = selected_method.find(f"./Parameter[@key='{key}']")
            if parameter is not None:
                parameter.text = value
    else:
        if fixed_size <= 0:
            raise ValueError("FIXED_SIZE_NOT_POSITIVE")
        size_parameter = selected_method.find("./Params/Param[@key='Size']")
        if size_parameter is None:
            raise ValueError("FIXED_SIZE_PARAMETER_MISSING")
        size_parameter.text = str(fixed_size)
    task_xml.find("./RiskMoneyManagement/MoneyManagement/InitialCapital").text = "10000"
    task_xml.find("./CrossChecks").set("use", "false")
    conditions = task_xml.find("./Rankings/Conditions"); conditions.clear()
    rankings = task_xml.find("./Rankings")
    rankings.set("type", "never")
    delete_failed = rankings.find("DeleteFailedStrategies")
    if delete_failed is None:
        delete_failed = ET.SubElement(rankings, "DeleteFailedStrategies")
    # Diagnostic runs retain rejected results so their executed metrics remain
    # inspectable. Production gates keep the historical delete-on-failure mode.
    delete_failed.text = "false" if keep_failed else "true"
    minimum_trades = methodology["temporal_validation"]["minimum_trades_oos"]
    minimum_pf = methodology["temporal_validation"]["minimum_oos_profit_factor"]
    conditions.extend([_condition("NumberOfTrades", "Integer", ">=", minimum_trades),
                       _condition("ProfitFactor", "Decimal2", ">=", minimum_pf)])
    task_xml.find("./Rankings/MaxStrategies").text = "1000"
    stop_condition = task_xml.find("./Rankings/StopCondition")
    stop_condition.set("type", "databank-full")
    stop_condition.set("passedStrategies", "1000")
    output_db = stage.capitalize()
    task_databanks = task_xml.find("./Databanks")
    _select_all_input_strategies(task_xml)
    task_databanks.find("./Databank[@name='Input']").set("value", "Results")
    task_databanks.find("./Databank[@name='Output']").set("value", output_db)

    config = ET.Element("Project", {"name": project_name, "version": "143.2708"})
    tasks = ET.SubElement(config, "Tasks")
    ET.SubElement(tasks, "Task", {"type": "Retest", "name": f"{stage} retest", "showSettingsOverview": "false",
        "sampleName": "Custom", "active": "true", "taskXMLFile": "Retest-Task1.xml"})
    databanks = ET.SubElement(config, "Databanks")
    for position, name in enumerate(("Results", output_db)):
        ET.SubElement(databanks, "Databank", {"name": name, "view": "Default - Main data",
            "syncType": "Auto-sync never", "position": str(position)})
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("config.xml", ET.tostring(config, encoding="utf-8"))
        archive.writestr("Retest-Task1.xml", ET.tostring(task_xml, encoding="utf-8"))
    result = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name, "stage": stage, "input_databank": "Results",
        "output_databank": output_db, "date_from": periods[start_key],
        "date_to": periods[end_key], "symbol": symbol, "timeframe": timeframe,
        "source_task_file": source_task_file, "money_management": method_type,
        "fixed_size": fixed_size if money_management == "fixed_size" else None,
        "source_cfx_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "resource_source": str(resource_source) if resource_source else None,
        "resource_task_file": resource_task_file if resource_source else None,
        "resource_source_sha256": hashlib.sha256(resource_source.read_bytes()).hexdigest() if resource_source else None,
        "setup_slippage": slippage,
        "test_precision": test_precision,
        "keep_failed": keep_failed,
        "risk_per_trade_pct": methodology["small_account"]["maximum_risk_per_trade_pct"] if money_management == "risk_percent" else None,
        "minimum_trades": minimum_trades,
        "minimum_profit_factor": minimum_pf, "holdout_locked": stage != "holdout",
        "cfx_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True); parser.add_argument("--stage", choices=PERIOD_KEYS, required=True)
    parser.add_argument("--discovery-manifest", type=Path, required=True)
    parser.add_argument("--symbol", required=True); parser.add_argument("--timeframe", required=True)
    parser.add_argument("--source-task-file", default="Retest-Task1.xml")
    parser.add_argument("--resource-source", type=Path)
    parser.add_argument("--resource-task-file", default="Build-Task1.xml")
    parser.add_argument("--slippage", type=float, default=0,
                        help="Slippage explícit en unitats SQ de l'instrument")
    parser.add_argument("--test-precision", type=int, default=4,
                        help="Precisió SQ explícita (1..4)")
    parser.add_argument("--money-management", choices=("risk_percent", "fixed_size"),
                        default="risk_percent")
    parser.add_argument("--fixed-size", type=float, default=1)
    parser.add_argument("--keep-failed", action="store_true",
                        help="Conserva resultats rebutjats per poder diagnosticar-ne les metriques")
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v1.json"))
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.output, args.name, args.stage,
        args.discovery_manifest, args.methodology, args.symbol, args.timeframe,
        args.source_task_file, args.resource_source, args.resource_task_file,
        args.slippage, args.test_precision, args.money_management,
        args.fixed_size, args.keep_failed), indent=2))

if __name__ == "__main__": main()
