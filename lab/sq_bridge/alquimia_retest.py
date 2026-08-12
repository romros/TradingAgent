#!/usr/bin/env python3
"""Genera un CFX Retest per una etapa temporal segellada d'Alquimia."""
from __future__ import annotations
import argparse
import hashlib
import json
import copy
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.methodology import validate
from lab.sq_bridge.sqx_extract import extract as extract_sqx

PERIOD_KEYS = {"train": ("train_from", "train_to"),
               "validation": ("validation_from", "validation_to"),
               "oos": ("oos_from", "oos_to"),
               "pre_holdout": ("train_from", "oos_to"),
               "holdout": ("holdout_from", "holdout_to")}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_reproducible_cfx(path: Path, members: dict[str, bytes]) -> None:
    """Write byte-identical CFX archives for identical XML members."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, payload)

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


def _normalize_venue_neutral_task(task_xml: ET.Element, symbol: str) -> None:
    """Make SQ a logic oracle; Ostium costs are applied after the retest."""
    for key in ("ExitAtEndOfDay", "ExitOnFriday"):
        matches = task_xml.findall(f"./Options/BuildTradingOptions/Params/Param[@key='{key}']")
        if len(matches) != 1:
            raise ValueError(f"VENUE_NEUTRAL_OPTION_MISSING: {key}")
        matches[0].text = "false"
    instruments = task_xml.findall(
        f"./Resources/Symbols/Symbol[@name='{symbol}']/InstrumentInfo")
    if len(instruments) != 1:
        raise ValueError("VENUE_NEUTRAL_INSTRUMENT_NOT_UNIQUE")
    instrument = instruments[0]
    instrument.set("defaultSpread", "0.0")
    instrument.set("defaultSlippage", "0.0")
    instrument.set(
        "commissions", '<Method type="None" use="true"><Params /></Method>')
    instrument.set(
        "swap", '<Swap use="false" type="money" long="0.0" short="0.0" '
                'tripleSwapOn="WEDNESDAY" rolloutHour="23:00" />')


def _candidate_contract(candidate_sqx: Path | None, candidate_id: str | None,
                        required: bool) -> dict:
    if candidate_sqx is None and candidate_id is None and not required:
        return {}
    if candidate_sqx is None or candidate_id is None:
        raise ValueError("CANDIDATE_SQX_AND_ID_REQUIRED")
    if not candidate_sqx.is_file():
        raise ValueError(f"CANDIDATE_SQX_MISSING: {candidate_sqx}")
    contract = extract_sqx(candidate_sqx)
    if contract.get("strategy_name") != candidate_id:
        raise ValueError(
            f"CANDIDATE_ID_MISMATCH: expected={candidate_id!r} "
            f"sqx={contract.get('strategy_name')!r}")
    if contract.get("translation_status") != "SUPPORTED_SUBSET":
        raise ValueError("CANDIDATE_NOT_TRANSLATABLE: " + ",".join(
            contract.get("unsupported_nodes_or_formulas", [])))
    return {
        "candidate_id": candidate_id,
        "candidate_sqx_path": str(candidate_sqx.resolve()),
        "candidate_sqx_sha256": _sha256(candidate_sqx),
        "candidate_strategy_xml_sha256": contract["strategy_xml_sha256"],
        "candidate_translation_status": contract["translation_status"],
    }


def _validate_uncensored_contract(task_xml: ET.Element, *, symbol: str,
                                  timeframe: str, date_from: str,
                                  date_to: str,
                                  output_databank: str = "PreHoldout") -> None:
    """Fail closed if SQ could censor or broaden an observation period."""
    setup = task_xml.find("./Data/Setups/Setup")
    charts = setup.findall("Chart") if setup is not None else []
    conditions = task_xml.findall("./Rankings/Conditions/Condition")
    delete_failed = task_xml.findtext("./Rankings/DeleteFailedStrategies")
    cross_checks = task_xml.find("./CrossChecks")
    databanks = task_xml.find("./Databanks")
    input_db = task_xml.find("./Databanks/Databank[@name='Input']")
    output_db = task_xml.find("./Databanks/Databank[@name='Output']")
    options = {node.get("key"): (node.text or "").strip().lower()
               for node in task_xml.findall("./Options/BuildTradingOptions/Params/Param")}
    instrument = task_xml.find(
        f"./Resources/Symbols/Symbol[@name='{symbol}']/InstrumentInfo")
    errors = []
    if setup is None or setup.get("dateFrom") != date_from.replace("-", "."):
        errors.append("DATE_FROM")
    if setup is None or setup.get("dateTo") != date_to.replace("-", "."):
        errors.append("DATE_TO")
    if len(charts) != 1 or charts[0].get("symbol") != symbol or charts[0].get("timeframe") != timeframe:
        errors.append("EXACT_MARKET")
    if len(charts) != 1 or charts[0].get("spread") != "0":
        errors.append("CHART_SPREAD_NOT_ZERO")
    if setup is None or setup.get("slippage") not in {"0", "0.0"}:
        errors.append("SLIPPAGE_NOT_ZERO")
    if options.get("ExitAtEndOfDay") != "false" or options.get("ExitOnFriday") != "false":
        errors.append("TIMED_EXITS_NOT_DISABLED")
    if (instrument is None or instrument.get("defaultSpread") not in {"0", "0.0"}
            or instrument.get("defaultSlippage") not in {"0", "0.0"}
            or 'type="None"' not in instrument.get("commissions", "")
            or 'use="false"' not in instrument.get("swap", "")):
        errors.append("INSTRUMENT_COSTS_NOT_NEUTRAL")
    if conditions:
        errors.append("PERFORMANCE_FILTERS_PRESENT")
    if delete_failed != "false":
        errors.append("DELETE_FAILED_ENABLED")
    if cross_checks is None or cross_checks.get("use") != "false":
        errors.append("CROSS_CHECKS_ENABLED")
    if databanks is None or databanks.get("retestSelected") != "false":
        errors.append("NOT_ALL_INPUT_STRATEGIES")
    if input_db is None or input_db.get("value") != "Results":
        errors.append("INPUT_DATABANK")
    if output_db is None or output_db.get("value") != output_databank:
        errors.append("OUTPUT_DATABANK")
    if errors:
        raise ValueError("UNCENSORED_RETEST_CONTRACT_INVALID: " + ",".join(errors))


# Backward-compatible name used by existing temporal tests and integrations.
def _validate_pre_holdout_contract(task_xml: ET.Element, *, symbol: str,
                                    timeframe: str, date_from: str,
                                    date_to: str) -> None:
    _validate_uncensored_contract(
        task_xml, symbol=symbol, timeframe=timeframe,
        date_from=date_from, date_to=date_to, output_databank="PreHoldout")


def verify_retest_project(cfx_path: Path, manifest: dict, *,
                          require_archive_hash: bool = True) -> dict:
    """Reopen a generated CFX and verify its frozen scientific contract."""
    if (manifest.get("schema_version") != 2
            or manifest.get("stage") != "pre_holdout"
            or (require_archive_hash and manifest.get("cfx_sha256") != _sha256(cfx_path))
            or manifest.get("build_reproducible") is not True
            or manifest.get("source_role") != "xml_format_scaffold_only"
            or manifest.get("performance_filters_applied_in_sq") is not False
            or manifest.get("holdout_accessed") is not False):
        raise ValueError("RETEST_MANIFEST_INVALID")
    candidate_path = Path(manifest.get("candidate_sqx_path", ""))
    candidate = _candidate_contract(
        candidate_path, manifest.get("candidate_id"), required=True)
    if any(candidate.get(key) != manifest.get(key) for key in candidate):
        raise ValueError("RETEST_CANDIDATE_LINEAGE_MISMATCH")
    with zipfile.ZipFile(cfx_path) as archive:
        if set(archive.namelist()) != {"config.xml", "Retest-Task1.xml"}:
            raise ValueError("RETEST_CFX_MEMBERS_INVALID")
        config = ET.fromstring(archive.read("config.xml"))
        task = ET.fromstring(archive.read("Retest-Task1.xml"))
    tasks = config.findall("./Tasks/Task")
    if (config.get("name") != manifest.get("project_name") or len(tasks) != 1
            or tasks[0].get("type") != "Retest"
            or tasks[0].get("active") != "true"
            or tasks[0].get("taskXMLFile") != "Retest-Task1.xml"):
        raise ValueError("RETEST_CONFIG_INVALID")
    _validate_pre_holdout_contract(
        task, symbol=manifest["symbol"], timeframe=manifest["timeframe"],
        date_from=manifest["date_from"], date_to=manifest["date_to"])
    if (task.find("./Data/Setups/Setup").get("slippage") != str(
            manifest["setup_slippage"])):
        raise ValueError("RETEST_SLIPPAGE_MISMATCH")
    return {
        "project_name": manifest["project_name"],
        "candidate_id": manifest["candidate_id"],
        "candidate_sqx_sha256": manifest["candidate_sqx_sha256"],
        "date_from": manifest["date_from"], "date_to": manifest["date_to"],
        "symbol": manifest["symbol"], "timeframe": manifest["timeframe"],
        "input_databank": "Results", "output_databank": "PreHoldout",
    }


def verify_holdout_project(cfx_path: Path, manifest: dict, *,
                           require_archive_hash: bool = True) -> dict:
    """Verify the sole uncensored SQ opening of a frozen final holdout."""
    if (manifest.get("schema_version") != 2
            or manifest.get("stage") != "holdout"
            or (require_archive_hash and manifest.get("cfx_sha256") != _sha256(cfx_path))
            or manifest.get("build_reproducible") is not True
            or manifest.get("source_role") != "xml_format_scaffold_only"
            or manifest.get("performance_filters_applied_in_sq") is not False
            or manifest.get("holdout_accessed") is not True
            or manifest.get("holdout_locked") is not False):
        raise ValueError("HOLDOUT_RETEST_MANIFEST_INVALID")
    release_path = Path(manifest.get("holdout_release_artifact_path", ""))
    if (not release_path.is_file()
            or manifest.get("holdout_release_artifact_sha256") != _sha256(release_path)):
        raise ValueError("HOLDOUT_RELEASE_ARTIFACT_INVALID")
    release = json.loads(release_path.read_text())
    if (release.get("stage") != "small_account_economics"
            or release.get("decision") != "PASS"
            or release.get("campaign_id") != manifest.get("holdout_release_campaign_id")
            or release.get("candidate_ids") != [manifest.get("candidate_id")]
            or release.get("holdout_accessed") is not False):
        raise ValueError("HOLDOUT_RELEASE_NOT_PROMOTABLE")
    candidate_path = Path(manifest.get("candidate_sqx_path", ""))
    candidate = _candidate_contract(
        candidate_path, manifest.get("candidate_id"), required=True)
    if any(candidate.get(key) != manifest.get(key) for key in candidate):
        raise ValueError("HOLDOUT_RETEST_CANDIDATE_LINEAGE_MISMATCH")
    with zipfile.ZipFile(cfx_path) as archive:
        if set(archive.namelist()) != {"config.xml", "Retest-Task1.xml"}:
            raise ValueError("HOLDOUT_RETEST_CFX_MEMBERS_INVALID")
        config = ET.fromstring(archive.read("config.xml"))
        task = ET.fromstring(archive.read("Retest-Task1.xml"))
    tasks = config.findall("./Tasks/Task")
    if (config.get("name") != manifest.get("project_name") or len(tasks) != 1
            or tasks[0].get("type") != "Retest"
            or tasks[0].get("active") != "true"):
        raise ValueError("HOLDOUT_RETEST_CONFIG_INVALID")
    _validate_uncensored_contract(
        task, symbol=manifest["symbol"], timeframe=manifest["timeframe"],
        date_from=manifest["date_from"], date_to=manifest["date_to"],
        output_databank="Holdout")
    return {
        "project_name": manifest["project_name"],
        "candidate_id": manifest["candidate_id"],
        "candidate_sqx_sha256": manifest["candidate_sqx_sha256"],
        "date_from": manifest["date_from"], "date_to": manifest["date_to"],
        "symbol": manifest["symbol"], "timeframe": manifest["timeframe"],
        "input_databank": "Results", "output_databank": "Holdout",
    }

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


INTRADAY_OPTION_KEYS = (
    "ExitAtEndOfDay", "EODExitTime", "LimitTimeRange",
    "SignalTimeRangeFrom", "SignalTimeRangeTo", "ExitAtEndOfRange",
    "MaxTradesPerDay",
)


def _graft_intraday_options(target: ET.Element, source: ET.Element) -> dict[str, str]:
    """Copy the effective discovery session contract into a Retest task."""
    source_params = {node.get("key"): node for node in source.findall(
        "./Options/BuildTradingOptions/Params/Param")}
    target_params = {node.get("key"): node for node in target.findall(
        "./Options/BuildTradingOptions/Params/Param")}
    missing = [key for key in INTRADAY_OPTION_KEYS
               if key not in source_params or key not in target_params]
    if missing:
        raise ValueError(f"INTRADAY_OPTIONS_MISSING: {missing}")
    copied = {}
    for key in INTRADAY_OPTION_KEYS:
        value = (source_params[key].text or "").strip()
        if not value:
            raise ValueError(f"INTRADAY_OPTION_EMPTY: {key}")
        target_params[key].text = value
        copied[key] = value
    intraday = (copied["ExitAtEndOfDay"] == "true"
                and copied["LimitTimeRange"] == "true"
                and copied["ExitAtEndOfRange"] == "true")
    daily = (copied["ExitAtEndOfDay"] == "false"
             and copied["LimitTimeRange"] == "false"
             and copied["ExitAtEndOfRange"] == "false")
    if (not (intraday or daily) or int(copied["MaxTradesPerDay"]) != 1):
        raise ValueError("INTRADAY_EXECUTION_CONTRACT_INVALID")
    return copied

def generate(source: Path, output: Path, project_name: str, stage: str, manifest_path: Path,
             methodology_path: Path, symbol: str, timeframe: str,
             source_task_file: str = "Retest-Task1.xml", resource_source: Path | None = None,
             resource_task_file: str = "Build-Task1.xml", slippage: float = 0,
             test_precision: int = 4, money_management: str = "risk_percent",
             fixed_size: float = 1, keep_failed: bool = False,
             candidate_sqx: Path | None = None,
             candidate_id: str | None = None,
             holdout_release_artifact: Path | None = None) -> dict:
    if stage not in PERIOD_KEYS:
        raise ValueError(f"Etapa invalida: {stage}")
    methodology = json.loads(methodology_path.read_text())
    errors = validate(methodology)
    if errors:
        raise ValueError("Metodologia invalida: " + "; ".join(errors))
    discovery = json.loads(manifest_path.read_text())
    is_v4 = methodology.get("schema_version", 1) >= 4
    if is_v4 and stage != "pre_holdout" and stage != "holdout":
        raise ValueError("V4_RETEST_STAGE_MUST_BE_PRE_HOLDOUT_OR_HOLDOUT")
    candidate = _candidate_contract(
        candidate_sqx, candidate_id, required=is_v4 or stage == "pre_holdout")
    periods = discovery.get("periods")
    required_periods = {key for pair in PERIOD_KEYS.values() for key in pair}
    if not isinstance(periods, dict) or not required_periods.issubset(periods):
        missing = sorted(required_periods - set(periods or {}))
        raise ValueError(f"DISCOVERY_PERIODS_MISSING: {missing}")
    if stage == "holdout" and not discovery.get("holdout_release_authorized", False):
        raise ValueError("HOLDOUT_LOCKED: cal autoritzacio explicita al manifest")
    release = {}
    if stage == "holdout":
        if holdout_release_artifact is None or not holdout_release_artifact.is_file():
            raise ValueError("HOLDOUT_RELEASE_ARTIFACT_REQUIRED")
        release_value = json.loads(holdout_release_artifact.read_text())
        if (release_value.get("stage") != "small_account_economics"
                or release_value.get("decision") != "PASS"
                or not isinstance(release_value.get("campaign_id"), str)
                or not release_value.get("campaign_id")
                or discovery.get("campaign_id") != release_value.get("campaign_id")
                or release_value.get("candidate_ids") != [candidate_id]
                or release_value.get("holdout_accessed") is not False):
            raise ValueError("HOLDOUT_RELEASE_NOT_PROMOTABLE")
        release = {
            "holdout_release_artifact_path": str(holdout_release_artifact.resolve()),
            "holdout_release_artifact_sha256": _sha256(holdout_release_artifact),
            "holdout_release_campaign_id": release_value["campaign_id"],
        }
    start_key, end_key = PERIOD_KEYS[stage]
    task_xml = _read_task(source, source_task_file)
    intraday_options = None
    if resource_source is not None:
        resource_task = _read_task(resource_source, resource_task_file)
        _graft_resource_symbol(task_xml, resource_task, symbol)
        intraday_options = _graft_intraday_options(task_xml, resource_task)
    _normalize_venue_neutral_task(task_xml, symbol)
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
    # Both pre-holdout and the one-shot final holdout must retain losing
    # candidates; otherwise SQ would censor the evidence needed for REJECT.
    uncensored = stage in {"pre_holdout", "holdout"}
    delete_failed.text = "false" if keep_failed or uncensored else "true"
    minimum_trades = methodology["temporal_validation"]["minimum_trades_oos"]
    minimum_pf = methodology["temporal_validation"]["minimum_oos_profit_factor"]
    maximum_dd_pct = methodology["temporal_validation"]["maximum_oos_drawdown_pct"]
    if not uncensored:
        conditions.extend([_condition("NumberOfTrades", "Integer", ">=", minimum_trades),
                           _condition("ProfitFactor", "Decimal2", ">=", minimum_pf),
                           _condition("DrawdownPct", "Decimal2Pct", "<=", maximum_dd_pct)])
    risk_management = task_xml.find("./RiskMoneyManagement/RiskManagement")
    if risk_management is None:
        raise ValueError("RISK_MANAGEMENT_MISSING")
    risk_management.set("maxDrawdown", str(maximum_dd_pct))
    task_xml.find("./Rankings/MaxStrategies").text = "1000"
    stop_condition = task_xml.find("./Rankings/StopCondition")
    stop_condition.set("type", "databank-full")
    stop_condition.set("passedStrategies", "1000")
    output_db = "PreHoldout" if stage == "pre_holdout" else stage.capitalize()
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
    if uncensored:
        _validate_uncensored_contract(
            task_xml, symbol=symbol, timeframe=timeframe,
            date_from=periods[start_key], date_to=periods[end_key],
            output_databank=output_db)
    _write_reproducible_cfx(output, {
        "config.xml": ET.tostring(config, encoding="utf-8"),
        "Retest-Task1.xml": ET.tostring(task_xml, encoding="utf-8"),
    })
    result = {"schema_version": 2,
        "project_name": project_name, "stage": stage, "input_databank": "Results",
        "output_databank": output_db, "date_from": periods[start_key],
        "date_to": periods[end_key], "symbol": symbol, "timeframe": timeframe,
        "source_task_file": source_task_file, "money_management": method_type,
        "fixed_size": fixed_size if money_management == "fixed_size" else None,
        "source_cfx_sha256": _sha256(source),
        "resource_source": str(resource_source) if resource_source else None,
        "resource_task_file": resource_task_file if resource_source else None,
        "resource_source_sha256": _sha256(resource_source) if resource_source else None,
        "intraday_execution_options": intraday_options,
        "setup_slippage": slippage,
        "test_precision": test_precision,
        "keep_failed": keep_failed or uncensored,
        "performance_filters_applied_in_sq": not uncensored,
        "all_input_strategies_selected": True,
        "risk_per_trade_pct": methodology["small_account"]["maximum_risk_per_trade_pct"] if money_management == "risk_percent" else None,
        "minimum_trades": minimum_trades,
        "minimum_profit_factor": minimum_pf,
        "maximum_drawdown_pct": maximum_dd_pct,
        "holdout_accessed": stage == "holdout",
        "holdout_locked": stage != "holdout",
        "build_reproducible": True,
        "source_role": "xml_format_scaffold_only",
        **release,
        **candidate,
        "cfx_sha256": _sha256(output)}
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
    parser.add_argument("--candidate-sqx", type=Path,
                        help="Unic SQX que el runner copiara al databank Results")
    parser.add_argument("--candidate-id",
                        help="StrategyName exacte esperat dins el SQX")
    parser.add_argument("--holdout-release-artifact", type=Path,
                        help="Artefacte PASS de small_account que obre el holdout")
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v1.json"))
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.output, args.name, args.stage,
        args.discovery_manifest, args.methodology, args.symbol, args.timeframe,
        args.source_task_file, args.resource_source, args.resource_task_file,
        args.slippage, args.test_precision, args.money_management,
        args.fixed_size, args.keep_failed, args.candidate_sqx,
        args.candidate_id, args.holdout_release_artifact), indent=2))

if __name__ == "__main__": main()
