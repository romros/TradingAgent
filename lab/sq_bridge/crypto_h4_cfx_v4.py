#!/usr/bin/env python3
"""Compile and structurally verify a native crypto H4 SQ 143.2708 CFX."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


COMMON_BLOCKS = {"EnterAtMarket",
                 "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss"}
SIGNAL_PARITY_EVIDENCE = Path(__file__).parent / "evidence/crypto_h4_sq_exact_signal_gap_parity_v4.json"
CUSTOM_SIGNAL_SOURCE = Path(__file__).parent / "sq_custom_blocks_v4/SQ/Utils/AlquimiaH4Signals.java"


def _mechanism_blocks(plan: dict[str, Any]) -> set[str]:
    if plan["mechanism"] == "channel_breakout":
        signal = "AlquimiaH4ChannelBelow" if plan["direction"] == "short" else "AlquimiaH4ChannelAbove"
        return COMMON_BLOCKS | {signal}
    if plan["mechanism"] == "time_series_momentum":
        signal = "AlquimiaH4MomentumBelow" if plan["direction"] == "short" else "AlquimiaH4MomentumAbove"
        return COMMON_BLOCKS | {signal}
    raise ValueError("ATR_PERCENTILE_CUSTOM_BLOCK_REQUIRED")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError(f"JSON object required: {path}")
    return value


def _set(root: ET.Element, path: str, value: Any) -> None:
    node = root.find(path)
    if node is None: raise ValueError(f"SQ scaffold field missing: {path}")
    node.text = str(value)


def _require_signal_parity() -> dict[str, Any]:
    evidence = _load(SIGNAL_PARITY_EVIDENCE)
    sources = evidence.get("source_sha256") or {}
    if (evidence.get("decision") != "PASS_EXACT_SQ_CHARTDATA_SIGNAL_PARITY"
            or evidence.get("differences") != 0
            or sources.get("SQ/Utils/AlquimiaH4Signals.java") != _sha(CUSTOM_SIGNAL_SOURCE)):
        raise ValueError("exact custom signal parity evidence missing or stale")
    return evidence


def _ensure_custom_signal_block(root: ET.Element, key: str) -> ET.Element:
    existing = root.find(f".//Block[@key='{key}']")
    if existing is not None: return existing
    blocks = root.find(".//BuildingBlocks")
    if blocks is None:
        native = root.find(".//Block[@key='ROCAboveLevel']")
        if native is None: raise ValueError("SQ scaffold building-block container missing")
        blocks = next(parent for parent in root.iter() if native in list(parent))
    block = ET.SubElement(blocks, "Block", {"key": key, "weight": "1", "use": "false",
                                            "category": "signals"})
    generated = ET.SubElement(block, "Generated", {"weight": "1"})
    for param_key, name, kind in (("#Chart#", "Chart", "data"),
                                  ("#Period#", "Period", "int")):
        attributes = {"key": param_key, "name": name, "type": kind,
                      "generation": "random"}
        if kind == "data": attributes["allCharts"] = "true"
        ET.SubElement(generated, "Param", attributes)
    if "Momentum" in key:
        ET.SubElement(generated, "Param", {"key": "#Level#", "name": "Level",
                                            "type": "double", "generation": "random"})
    ET.SubElement(generated, "Param", {"key": "#Shift#", "name": "Shift",
                                        "type": "int", "generation": "random"})
    ET.SubElement(block, "Predefined", {"changed": "true"})
    return block


def _write_cfx(path: Path, members: list[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3; info.external_attr = 0o100600 << 16
            archive.writestr(info, payload)


def _utc_ms(day: str, *, end: bool = False) -> str:
    stamp = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end: stamp = stamp.replace(hour=20)
    return str(int(stamp.timestamp() * 1000))


def _configure_mm(root: ET.Element, plan: dict[str, Any]) -> None:
    mm = root.find("./RiskMoneyManagement/MoneyManagement")
    if mm is None: raise ValueError("SQ scaffold money management missing")
    _set(root, "./RiskMoneyManagement/MoneyManagement/InitialCapital", 200)
    for method in mm.findall("Method"): method.set("use", "false")
    crypto = next((row for row in mm.findall("Method")
                   if row.get("type") == "CryptoSizeByPrice"), None)
    if crypto is None:
        crypto = ET.SubElement(mm, "Method", {"type": "CryptoSizeByPrice", "use": "false"})
        params = ET.SubElement(crypto, "Params")
        for key in ("UseAccountBalance", "MaxSize", "Decimals"):
            ET.SubElement(params, "Param", {"key": key, "className": "CryptoSizeByPrice"})
    crypto.set("use", "true")
    values = {"UseAccountBalance": "false",
              "MaxSize": str(plan["money_management"]["maximum_size"]),
              "Decimals": str(plan["money_management"]["decimals"])}
    for key, value in values.items():
        param = crypto.find(f"./Params/Param[@key='{key}']")
        if param is None: raise ValueError(f"CryptoSizeByPrice parameter missing: {key}")
        param.set("className", "CryptoSizeByPrice"); param.text = value


def _configure_zero_commission(setup: ET.Element) -> None:
    """Encode gross research costs in the native SQ 143 representation."""
    commissions = setup.find("./Commissions")
    if commissions is None:
        raise ValueError("SQ scaffold commissions missing")
    commissions.clear()
    method = ET.SubElement(commissions, "Method", {"type": "PerTrade", "use": "true"})
    params = ET.SubElement(method, "Params")
    ET.SubElement(params, "Param", {
        "key": "Commission", "className": "PerTrade"}).text = "0"


def _configure_resource(root: ET.Element, plan: dict[str, Any]) -> None:
    resources = root.find("./Resources/Symbols")
    if resources is None:
        raise ValueError("SQ scaffold symbol resources missing")
    symbols = resources.findall("Symbol")
    if not symbols:
        raise ValueError("SQ scaffold has no clonable symbol resource")
    for symbol in symbols[1:]:
        resources.remove(symbol)
    resource = symbols[0]
    resource.clear()
    resource.attrib.update({
        "name": plan["symbol"], "source": "1", "barType": "1", "precision": "H4",
        "timezone": "Etc/UTC", "dateFrom": _utc_ms(plan["periods"]["train_from"]),
        "dateTo": _utc_ms(plan["periods"]["train_to"], end=True),
        "uSymbol": f"{plan['market']}_ALQ", "uSymbolName": f"{plan['market']}_ALQ",
        "removeWeekends": "false", "broker": "-1"})
    step = "0.0001" if plan["market"] == "BTCUSD" else "0.001"
    ET.SubElement(resource, "InstrumentInfo", {
        "instrument": plan["instrument"], "description": "Alquimia gross crypto proxy",
        "tickSize": "0.01", "tickStep": "0.01", "minDistance": "0.0",
        "tickValueInMoney": "0.0", "dateFrom": "0", "dateTo": "0",
        "rows": "0", "totalDays": "0", "defaultSpread": "0.0",
        "defaultSlippage": "0.0", "decimals": "2",
        "commissions": ('<Method type="PerTrade" use="true"><Params>'
                        '<Param key="Commission" className="PerTrade">0</Param>'
                        '</Params></Method>'),
        "pointValue": "1.0", "dataType": "7", "recognizedFromOrders": "false",
        "exchange": "", "country": "", "sector": "Crypto",
        "swap": ('<Swap use="false" type="money" long="0" short="0" '
                 'tripleSwapOn="NEVER" />'),
        "orderSizeMultiplier": "1.0", "orderSizeStep": step, "broker": "-1"})


def compile_cfx(plan_path: Path, scaffold_path: Path, output_path: Path) -> dict[str, Any]:
    plan_path, scaffold_path = plan_path.resolve(), scaffold_path.resolve()
    plan = _load(plan_path)
    parity = _require_signal_parity()
    if plan.get("decision") != "PASS_SQ_PLAN_READY":
        raise ValueError("CFX plan is not replay verified")
    if plan.get("mechanism") not in {"channel_breakout", "time_series_momentum"}:
        if plan.get("mechanism") == "volatility_compression_breakout":
            raise ValueError("ATR_PERCENTILE_CUSTOM_BLOCK_REQUIRED")
        raise ValueError("CFX plan mechanism is unsupported")
    if (plan.get("attempt_budget"), plan.get("sq_genetic_shape"),
            plan.get("initial_capital_usdc"), plan.get("discovery_leverage")) != (
            10_000, {"islands": 4, "population_per_island": 100,
                     "max_generations": 25, "nominal_evaluations": 10_000}, 200, 1):
        raise ValueError("CFX genetic/small-account contract changed")
    if (plan.get("attempt_stop_guard"), plan.get("wall_time_budget_minutes"),
            plan.get("accepted_limit")) != (64, 240, 1):
        raise ValueError("CFX supervised stop contract changed")
    if plan.get("money_management") != {
            "method": "CryptoSizeByPrice", "use_account_balance": False,
            "maximum_size": 100, "decimals": 4 if plan["market"] == "BTCUSD" else 3,
            "fallback_to_size_one_allowed": False}:
        raise ValueError("CFX CryptoSizeByPrice contract changed")
    with zipfile.ZipFile(scaffold_path) as archive:
        names = archive.namelist()
        config = ET.fromstring(archive.read("config.xml"))
        tasks = [row for row in config.findall("./Tasks/Task") if row.get("type") == "Build"]
        if len(tasks) != 1: raise ValueError("SQ scaffold requires exactly one Build task")
        task_name = tasks[0].get("taskXMLFile")
        if not task_name or names.count(task_name) != 1: raise ValueError("SQ scaffold task invalid")
        root = ET.fromstring(archive.read(task_name))
    tasks_parent = config.find("./Tasks")
    for row in list(tasks_parent):
        if row is not tasks[0]: tasks_parent.remove(row)
    config.set("name", plan["project_name"])
    mode = root.find("./WhatToBuild/BuildMode")
    mode.set("generationType", "genetic-evolution")
    shape = plan["sq_genetic_shape"]; genetic = plan["genetic_parameters"]
    for path, value in {
        "./WhatToBuild/BuildMode/PopulationSize": shape["population_per_island"],
        "./WhatToBuild/BuildMode/MaxGenerations": shape["max_generations"],
        "./WhatToBuild/BuildMode/Islands": shape["islands"],
        "./WhatToBuild/BuildMode/DecimationCoef": 1,
        "./WhatToBuild/BuildMode/CrossoverProbability": genetic["crossover_probability_pct"],
        "./WhatToBuild/BuildMode/MutationProbability": genetic["mutation_probability_pct"],
        "./WhatToBuild/BuildMode/MigrationModulo": genetic["migration_every_generations"],
        "./WhatToBuild/BuildMode/MigrationRate": genetic["migration_rate_pct"],
        "./WhatToBuild/BuildMode/InitGenerationType": genetic["initial_population_mode"],
        "./WhatToBuild/SLPTOptions/SLRequired": "true",
        "./WhatToBuild/SLPTOptions/SLATR": "true",
        "./WhatToBuild/SLPTOptions/PTRequired": "false",
        "./RiskMoneyManagement/MoneyManagement/InitialCapital": 200,
        "./Rankings/MaxStrategies": 1,
    }.items(): _set(root, path, value)
    for name in ("EvoRestartOnFinish", "EvoRestartOnStagnation"):
        node = mode.find(name)
        if node is None: raise ValueError(f"SQ scaffold missing {name}")
        node.set("status", "false")
    space = plan["parameter_search_space"]
    for path, value in {
        "./WhatToBuild/SLPTOptions/MinSLATRMultiple": space["atr_stop_multiple"]["minimum"],
        "./WhatToBuild/SLPTOptions/MaxSLATRMultiple": space["atr_stop_multiple"]["maximum"],
        "./WhatToBuild/SLPTOptions/MinSLATRPeriod": 14,
        "./WhatToBuild/SLPTOptions/MaxSLATRPeriod": 14,
    }.items(): _set(root, path, value)
    complexity = root.find("./WhatToBuild/RulesComplexity")
    complexity.clear(); complexity.set("useDifferentSettings", "false")
    ET.SubElement(complexity, "Chart", {"name": "Main chart", "minConditions": "1",
        "maxConditions": "1", "minExitConditions": "0", "maxExitConditions": "0",
        "minExitTypes": "2", "maxExitTypes": "2",
        "minPeriod": str(space["indicator_period"]["minimum"]),
        "maxPeriod": str(space["indicator_period"]["maximum"]),
        "minShift": str(space["shift"]["minimum"]),
        "maxShift": str(space["shift"]["maximum"])})
    sides = root.find("./WhatToBuild/MarketSides"); sides.set("type", plan["direction"])
    symmetry = "true" if plan["direction"] == "both" else "false"
    _set(root, "./WhatToBuild/MarketSides/EntrySymmetry", symmetry)
    _set(root, "./WhatToBuild/MarketSides/ExitSymmetry", symmetry)
    setup = root.find("./Data/Setups/Setup")
    setup.set("dateFrom", plan["periods"]["train_from"].replace("-", "."))
    setup.set("dateTo", plan["periods"]["train_to"].replace("-", "."))
    setup.set("slippage", "0"); setup.set("testPrecision", "2")
    charts = setup.findall("Chart")
    for chart in charts[1:]: setup.remove(chart)
    charts[0].set("symbol", plan["symbol"]); charts[0].set("timeframe", "H4")
    charts[0].set("spread", "0")
    _configure_zero_commission(setup)
    _configure_resource(root, plan)
    expected_blocks = _mechanism_blocks(plan)
    for key in expected_blocks:
        if key.startswith("AlquimiaH4"): _ensure_custom_signal_block(root, key)
    for block in root.findall(".//Block"):
        block.set("use", "true" if block.get("key") in expected_blocks else "false")
        block.set("weight", "1")
    blocks = {row.get("key"): row for row in root.findall(".//Block")
              if row.get("use") == "true"}
    if set(blocks) != expected_blocks: raise ValueError("SQ scaffold lacks mechanism blocks")
    signal_key = next(key for key in blocks if key.startswith("AlquimiaH4"))
    signal = blocks[signal_key]
    parameter_map = {"#Period#": (space["indicator_period"]["minimum"],
                                    space["indicator_period"]["maximum"], 1),
                     "#Shift#": (space["shift"]["minimum"], space["shift"]["maximum"], 1)}
    if plan["mechanism"] == "time_series_momentum":
        parameter_map["#Level#"] = (space["roc_threshold_pct"]["minimum"],
                                      space["roc_threshold_pct"]["maximum"], .5)
    for key, (minimum, maximum, step) in parameter_map.items():
        param = signal.find(f"./Generated/Param[@key='{key}']")
        if param is None: raise ValueError(f"SQ custom signal parameter missing: {key}")
        param.attrib.update({"generation": "random", "minValue": str(minimum),
                             "maxValue": str(maximum), "step": str(step)})
        param.attrib.pop("defaultValue", None)
    predefined = signal.find("Predefined")
    predefined.clear(); predefined.set("changed", "true")
    exit_param = blocks["ExitAfterBars.ExitAfterBars"].find(
        ".//Generated/Param[@key='#ExitAfterBars#']")
    exit_param.attrib.update({"minValue": str(space["exit_after_bars"]["minimum"]),
                              "maxValue": str(space["exit_after_bars"]["maximum"]),
                              "step": "1"})
    blocks["ExitAfterBars.ExitAfterBars"].set("probability", "100")
    blocks["StopLoss.StopLoss"].set("probability", "100")
    _configure_mm(root, plan)
    cross = root.find("./CrossChecks")
    if cross is not None: cross.set("use", "false")
    ranking = root.find("./Rankings/FitnessCriteria/Settings/Ranking")
    ranking.set("type", "ReturnDDRatio")
    stop = root.find("./Rankings/StopCondition")
    stop.attrib.update({"type": "databank-full", "passedStrategies": "1",
                        "restartCount": "0", "days": "0",
                        "hours": str(plan["wall_time_budget_minutes"] // 60),
                        "minutes": str(plan["wall_time_budget_minutes"] % 60)})
    config_xml, task_xml = (ET.tostring(node, encoding="utf-8") for node in (config, root))
    _write_cfx(output_path.resolve(), [("config.xml", config_xml), (task_name, task_xml)])
    manifest = {**plan, "decision": "PASS_CFX_COMPILED",
                "plan_path": str(plan_path), "plan_sha256": _sha(plan_path),
                "format_scaffold_path": str(scaffold_path),
                "format_scaffold_sha256": _sha(scaffold_path),
                "cfx_path": str(output_path.resolve()), "cfx_sha256": _sha(output_path.resolve()),
                "enabled_blocks": sorted(expected_blocks),
                "translation_scope": "sq_proposal_generation_only",
                "custom_signal_parity_evidence": str(SIGNAL_PARITY_EVIDENCE.resolve()),
                "custom_signal_parity_evidence_sha256": _sha(SIGNAL_PARITY_EVIDENCE),
                "known_semantic_differences": [
                    "SQ_NATIVE_ATR_WILDER_VS_ALQUIMIA_SMA14_DURING_PROPOSAL_SEARCH",
                    "SQ_OPEN_TRADES_CAN_CROSS_CANONICAL_DATA_GAPS_UNTIL_SEGMENTED_RETEST"],
                "python_parity_required": True,
                "strategy_promotion_authorized": False,
                "sqcli_authorized": False}
    manifest_path = output_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    verify_cfx(output_path.resolve(), manifest)
    return manifest


def verify_cfx(path: Path, manifest: dict[str, Any], *,
               require_archive_hash: bool = True) -> dict[str, Any]:
    if (manifest.get("translation_scope") != "sq_proposal_generation_only"
            or manifest.get("known_semantic_differences") != [
                "SQ_NATIVE_ATR_WILDER_VS_ALQUIMIA_SMA14_DURING_PROPOSAL_SEARCH",
                "SQ_OPEN_TRADES_CAN_CROSS_CANONICAL_DATA_GAPS_UNTIL_SEGMENTED_RETEST"]
            or manifest.get("custom_signal_parity_evidence_sha256") != _sha(SIGNAL_PARITY_EVIDENCE)
            or manifest.get("python_parity_required") is not True
            or manifest.get("strategy_promotion_authorized") is not False):
        raise ValueError("CFX proposal-only translation contract")
    if require_archive_hash and _sha(path) != manifest.get("cfx_sha256"):
        raise ValueError("CFX artifact hash contract")
    with zipfile.ZipFile(path) as archive:
        config = ET.fromstring(archive.read("config.xml"))
        tasks = config.findall("./Tasks/Task")
        if len(tasks) != 1 or tasks[0].get("type") != "Build": raise ValueError("CFX task contract")
        root = ET.fromstring(archive.read(tasks[0].get("taskXMLFile")))
    if config.get("name") != manifest["project_name"]:
        raise ValueError("CFX project name contract")
    mode = root.find("./WhatToBuild/BuildMode")
    shape = (int(mode.findtext("Islands")), int(mode.findtext("PopulationSize")),
             int(mode.findtext("MaxGenerations")))
    if mode.get("generationType") != "genetic-evolution" or shape != (4, 100, 25):
        raise ValueError("CFX genetic contract")
    genetic = manifest["genetic_parameters"]
    actual_genetic = {
        "CrossoverProbability": genetic["crossover_probability_pct"],
        "MutationProbability": genetic["mutation_probability_pct"],
        "MigrationModulo": genetic["migration_every_generations"],
        "MigrationRate": genetic["migration_rate_pct"],
        "InitGenerationType": genetic["initial_population_mode"],
        "DecimationCoef": 1,
    }
    if any(mode.findtext(key) != str(value) for key, value in actual_genetic.items()):
        raise ValueError("CFX genetic parameter contract")
    if any(mode.find(key) is None or mode.find(key).get("status") != "false"
           for key in ("EvoRestartOnFinish", "EvoRestartOnStagnation")):
        raise ValueError("CFX genetic restart contract")
    setup = root.find("./Data/Setups/Setup"); chart = setup.findall("Chart")
    if (len(chart) != 1 or chart[0].get("symbol") != manifest["symbol"]
            or chart[0].get("timeframe") != "H4" or chart[0].get("spread") != "0"
            or setup.get("slippage") != "0" or setup.get("testPrecision") != "2"
            or setup.get("dateFrom") != manifest["periods"]["train_from"].replace("-", ".")
            or setup.get("dateTo") != manifest["periods"]["train_to"].replace("-", ".")):
        raise ValueError("CFX data contract")
    commissions = setup.findall("./Commissions/Method")
    if (len(commissions) != 1 or commissions[0].get("type") != "PerTrade"
            or commissions[0].get("use") != "true"
            or commissions[0].findtext("./Params/Param[@key='Commission']") != "0"):
        raise ValueError("CFX gross commission contract")
    if root.findtext("./RiskMoneyManagement/MoneyManagement/InitialCapital") != "200":
        raise ValueError("CFX initial capital contract")
    active_mm = [row for row in root.findall("./RiskMoneyManagement/MoneyManagement/Method")
                 if row.get("use") == "true"]
    if len(active_mm) != 1 or active_mm[0].get("type") != "CryptoSizeByPrice":
        raise ValueError("CFX crypto MM missing")
    params = {row.get("key"): row.text for row in active_mm[0].findall("./Params/Param")}
    if params != {"UseAccountBalance": "false", "MaxSize": "100",
                  "Decimals": str(manifest["money_management"]["decimals"])}:
        raise ValueError("CFX crypto MM parameters")
    enabled = {row.get("key") for row in root.findall(".//Block") if row.get("use") == "true"}
    expected_blocks = _mechanism_blocks(manifest)
    if enabled != expected_blocks: raise ValueError("CFX mechanism block contract")
    block_map = {row.get("key"): row for row in root.findall(".//Block")}
    space = manifest["parameter_search_space"]
    signal_key = next(key for key in enabled if key.startswith("AlquimiaH4"))
    signal = block_map[signal_key]
    expected_parameters = {"#Period#": (space["indicator_period"]["minimum"],
                                         space["indicator_period"]["maximum"], 1),
                           "#Shift#": (space["shift"]["minimum"],
                                        space["shift"]["maximum"], 1)}
    if manifest["mechanism"] == "time_series_momentum":
        expected_parameters["#Level#"] = (space["roc_threshold_pct"]["minimum"],
                                            space["roc_threshold_pct"]["maximum"], .5)
    for key, (minimum, maximum, step) in expected_parameters.items():
            param = signal.find(f"./Generated/Param[@key='{key}']")
            if (param is None or param.get("generation") != "random"
                    or param.get("minValue") != str(minimum)
                    or param.get("maxValue") != str(maximum)
                    or param.get("step") != str(step)):
                raise ValueError("CFX custom signal parameter contract")
    predefined = signal.find("Predefined")
    if predefined is None or list(predefined):
        raise ValueError("CFX custom signal predefined parameter escape")
    exit_param = block_map["ExitAfterBars.ExitAfterBars"].find(
        ".//Generated/Param[@key='#ExitAfterBars#']")
    if (exit_param is None
            or exit_param.get("minValue") != str(space["exit_after_bars"]["minimum"])
            or exit_param.get("maxValue") != str(space["exit_after_bars"]["maximum"])
            or exit_param.get("step") != "1"):
        raise ValueError("CFX timed exit contract")
    slpt = root.find("./WhatToBuild/SLPTOptions")
    expected_sl = {
        "SLRequired": "true", "SLATR": "true", "PTRequired": "false",
        "MinSLATRPeriod": "14", "MaxSLATRPeriod": "14",
        "MinSLATRMultiple": str(space["atr_stop_multiple"]["minimum"]),
        "MaxSLATRMultiple": str(space["atr_stop_multiple"]["maximum"]),
    }
    if any(slpt.findtext(key) != value for key, value in expected_sl.items()):
        raise ValueError("CFX ATR stop contract")
    sides = root.find("./WhatToBuild/MarketSides")
    symmetry = "true" if manifest["direction"] == "both" else "false"
    if (sides.get("type") != manifest["direction"]
            or sides.findtext("EntrySymmetry") != symmetry
            or sides.findtext("ExitSymmetry") != symmetry):
        raise ValueError("CFX market-side contract")
    symbols = root.findall("./Resources/Symbols/Symbol")
    if len(symbols) != 1:
        raise ValueError("CFX symbol resource count contract")
    symbol = symbols[0]; info = symbol.find("InstrumentInfo")
    step = "0.0001" if manifest["market"] == "BTCUSD" else "0.001"
    if (symbol.get("name") != manifest["symbol"] or symbol.get("precision") != "H4"
            or symbol.get("timezone") != "Etc/UTC" or symbol.get("source") != "1"
            or symbol.get("uSymbol") != f"{manifest['market']}_ALQ"
            or info is None or info.get("instrument") != manifest["instrument"]
            or info.get("pointValue") != "1.0" or info.get("orderSizeStep") != step
            or info.get("dataType") != "7"
            or info.get("defaultSpread") != "0.0"
            or info.get("defaultSlippage") != "0.0"):
        raise ValueError("CFX proxy resource contract")
    stop = root.find("./Rankings/StopCondition")
    minutes = manifest["wall_time_budget_minutes"]
    if (stop.get("type") != "databank-full" or stop.get("passedStrategies") != "1"
            or stop.get("restartCount") != "0"
            or stop.get("hours") != str(minutes // 60)
            or stop.get("minutes") != str(minutes % 60)):
        raise ValueError("CFX stop condition contract")
    cross = root.find("./CrossChecks")
    if cross is not None and cross.get("use") != "false":
        raise ValueError("CFX cross-check contract")
    return {"valid": True, "shape": shape, "enabled_blocks": sorted(enabled),
            "money_management": params}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--scaffold", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compile_cfx(args.plan, args.scaffold, args.output)
    print(json.dumps({key: result[key] for key in (
        "decision", "project_name", "cfx_sha256", "enabled_blocks",
        "sqcli_authorized")}, indent=2))


if __name__ == "__main__": main()
