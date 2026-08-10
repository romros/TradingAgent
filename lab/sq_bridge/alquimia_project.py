#!/usr/bin/env python3
"""Genera un projecte SQ discovery auditable amb metodologia Alquimia."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from methodology import validate
from lab.sq_bridge.evidence_chain import verify as verify_chain
from lab.sq_bridge.temporal_split_contract_v4 import (
    digest as temporal_contract_digest,
    sq_periods,
)

TRANSLATABLE_BLOCKS = {
    "Prices.High", "Prices.Low", "Prices.Close",
    "Indicators.talib_SMA", "Indicators.talib_EMA", "Indicators.talib_RSI",
    "Indicators.talib_ROC", "Indicators.SMA", "Indicators.EMA",
    "Indicators.RSI", "Indicators.ROC", "Indicators.Highest", "Indicators.Lowest",
    "IsLower", "IsGreater", "CrossesAbove", "CrossesBelow", "IsFalling", "IsRising",
    "BarDayOfWeekIs", "BarDayOfMonth", "IsMonthFirstTradingDay",
    "IsMonthLastTradingDay",
    "EnterAtMarket", "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget",
    "StopLoss.StopLoss",
}

SEARCH_PROFILES = {
    "generic_translatable": TRANSLATABLE_BLOCKS,
    # Falsifiable XAU hypothesis: continuation after a recent channel break,
    # optionally confirmed by strength/volatility, with volatility-scaled risk.
    "xau_h4_channel_breakout_v1": {
        "Prices.Close", "Prices.High", "Prices.Low",
        "Indicators.Highest", "Indicators.Lowest", "Indicators.ATR",
        "Indicators.ADX", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget",
        "StopLoss.StopLoss",
    },
    "xau_h4_stop_channel_breakout_v2": {
        "Indicators.ADX", "Indicators.ATR", "Indicators.ROC",
        "IsGreater", "IsLower", "IsRising", "IsFalling",
        "EnterAtStop", "Stop/Limit Price Levels.Highest",
        "Stop/Limit Price Levels.Lowest", "Stop/Limit Price Ranges.ATR",
        "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget",
        "StopLoss.StopLoss",
    },
    "xau_h4_atr_compression_breakout_v3": {
        "Indicators.ATR", "IsFalling",
        "EnterAtStop", "Stop/Limit Price Levels.Highest",
        "Stop/Limit Price Levels.Lowest", "Stop/Limit Price Ranges.ATR",
        "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget",
        "StopLoss.StopLoss",
    },
    "xau_h4_sweep_reclaim_v4": {
        "Prices.Close", "Prices.High", "Prices.Low",
        "Indicators.Highest", "Indicators.Lowest", "Indicators.ATR",
        "IsGreater", "IsLower", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget",
        "StopLoss.StopLoss",
    },
    "msft_d1_close_trend_v1": {
        "Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.RSI",
        "Indicators.ROC", "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "EnterAtMarket", "ExitAfterBars.ExitAfterBars",
        "ProfitTarget.ProfitTarget", "StopLoss.StopLoss",
    },
    "msft_d1_close_calendar_v1": {
        "Prices.Close", "Indicators.EMA", "Indicators.RSI", "IsGreater", "IsLower",
        "BarDayOfWeekIs", "BarDayOfMonth",
        "IsMonthFirstTradingDay", "IsMonthLastTradingDay", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "ProfitTarget.ProfitTarget", "StopLoss.StopLoss",
    },
    "eurusd_d1_breakout_v4": {
        "Prices.Close", "Prices.High", "Prices.Low",
        "Indicators.Highest", "Indicators.Lowest",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "EnterAtMarket", "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
    "eurusd_d1_momentum_v4": {
        "Prices.Close", "Indicators.SMA", "Indicators.EMA", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
    "eurusd_d1_shock_reversion_v4": {
        "Prices.Close", "Indicators.RSI", "Indicators.ROC",
        "IsGreater", "IsLower", "CrossesAbove", "CrossesBelow",
        "IsRising", "IsFalling", "EnterAtMarket",
        "ExitAfterBars.ExitAfterBars", "StopLoss.StopLoss",
    },
}

V4_HYPOTHESIS_SEARCH_PROFILES = {
    "d1_breakout": "eurusd_d1_breakout_v4",
    "d1_momentum": "eurusd_d1_momentum_v4",
    "d1_shock_reversion": "eurusd_d1_shock_reversion_v4",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_reproducible_cfx(path: Path, members: dict[str, bytes]) -> None:
    """Write byte-identical CFX archives for identical XML members."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, payload)


def _set_text(root: ET.Element, path: str, value: object) -> None:
    node = root.find(path)
    if node is None:
        raise ValueError(f"Camp SQ absent: {path}")
    node.text = str(value)


def _sq_discovery_slippage(market: dict, methodology: dict) -> float:
    # V4 evaluates gross price returns. Venue costs are frozen and applied once
    # downstream; embedding historical SQ slippage here would double charge it.
    if methodology.get("schema_version", 1) >= 4:
        return 0
    return market.get("discovery_slippage", 400)


def _validate_generation_contract(
    methodology: dict, generation_type: str, attempt_budget: int | None,
) -> None:
    if methodology.get("schema_version", 1) < 4:
        return
    generation = methodology["sq_generation"]
    expected = generation["search_method"].replace("_", "-")
    if generation_type != expected:
        raise ValueError(f"V4_GENERATION_TYPE expected={expected} got={generation_type}")
    if (not isinstance(attempt_budget, int) or isinstance(attempt_budget, bool)
            or not 1 <= attempt_budget <= generation["maximum_attempts"]):
        raise ValueError(
            f"V4_ATTEMPT_BUDGET must be 1..{generation['maximum_attempts']}")


def _nominal_genetic_shape(attempt_budget: int) -> dict[str, int]:
    """Choose an SQ genetic shape whose nominal population fits the budget.

    This product is not a hard attempt ceiling: SQ may generate replacements
    while filling the filtered initial population.  Prefer four islands for
    diversity when an exact nominal representation exists.
    """
    if (not isinstance(attempt_budget, int) or isinstance(attempt_budget, bool)
            or attempt_budget < 1):
        raise ValueError("attempt_budget must be a positive integer")
    choices = []
    for islands in range(1, 5):
        for population in range(1, 101):
            generations = min(100, attempt_budget // (islands * population))
            if generations:
                nominal = islands * population * generations
                choices.append((nominal, nominal == attempt_budget, islands,
                                population, generations))
    nominal, _exact, islands, population, generations = max(
        choices, key=lambda row: (row[0], row[1], row[2], row[3]))
    return {"islands": islands, "population_per_island": population,
            "max_generations": generations, "nominal_evaluations": nominal}


def _validate_v4_prerequisites(methodology: dict, methodology_path: Path,
                               chain_path: Path | None, campaign_id: str | None,
                               hypothesis_id: str | None, market_key: str) -> dict:
    if methodology.get("schema_version", 1) < 4:
        return {}
    if chain_path is None or not campaign_id or not hypothesis_id:
        raise ValueError("V4_SQ_PREREQUISITES_REQUIRED")
    chain = json.loads(chain_path.read_text())
    verification = verify_chain(chain, methodology_path)
    if (not verification.get("valid") or verification.get("terminal")
            or verification.get("next_stage") != "sq_generation"
            or verification.get("promotable") is not True):
        raise ValueError("V4_SQ_CHAIN_NOT_READY: " + ";".join(
            verification.get("errors", [])))
    if (chain.get("campaign_id"), chain.get("hypothesis_id"), chain.get("market")) != (
            campaign_id, hypothesis_id, market_key):
        raise ValueError("V4_SQ_CHAIN_IDENTITY_MISMATCH")
    receipts = chain.get("receipts")
    if (not isinstance(receipts, list) or [row.get("stage") for row in receipts]
            != ["market_preflight", "hypothesis_screen"]
            or any(row.get("decision") != "PASS" for row in receipts)):
        raise ValueError("V4_SQ_PREREQUISITE_RECEIPTS_INVALID")
    screen_path = Path(receipts[-1]["artifact"])
    screen = json.loads(screen_path.read_text())
    if hypothesis_id not in screen.get("selected_hypothesis_ids", []):
        raise ValueError("V4_SQ_HYPOTHESIS_NOT_SCREENED")
    expected_temporal_contract_sha256 = None
    if market_key == "EURUSD" and hypothesis_id in V4_HYPOTHESIS_SEARCH_PROFILES:
        trace_path = Path(screen.get("hypothesis_screen_trace_path", ""))
        trace_path = (trace_path if trace_path.is_absolute()
                      else screen_path.resolve().parent / trace_path)
        if (not trace_path.is_file()
                or screen.get("hypothesis_screen_trace_sha256")
                    != _sha256(trace_path.read_bytes())):
            raise ValueError("V4_SQ_SCREEN_TRACE_INVALID")
        trace = json.loads(trace_path.read_text())
        expected_temporal_contract_sha256 = trace.get("temporal_contract_sha256")
        if not isinstance(expected_temporal_contract_sha256, str):
            raise ValueError("V4_SQ_TEMPORAL_CONTRACT_MISSING")
    return {
        "campaign_id": campaign_id, "source_hypothesis_id": hypothesis_id,
        "evidence_chain_path": str(chain_path.resolve()),
        "evidence_chain_sha256": _sha256(chain_path.read_bytes()),
        "market_preflight_receipt_sha256": receipts[0]["receipt_sha256"],
        "hypothesis_screen_receipt_sha256": receipts[1]["receipt_sha256"],
        "_expected_temporal_contract_sha256": expected_temporal_contract_sha256,
        "_prerequisite_chain_snapshot": chain,
    }

def _require_resource_symbol(root: ET.Element, symbol: str, market: dict) -> None:
    resources = root.findall("./Resources/Symbols/Symbol")
    matches = [node for node in resources if node.get("name") == symbol]
    if not matches and market.get("sq_resource_clone_from"):
        matches = [node for node in resources
                   if node.get("name") == market["sq_resource_clone_from"]]
        if len(matches) == 1:
            matches[0].attrib.update(market.get("sq_resource_attributes", {}))
            for attribute in market.get("sq_resource_remove_attributes", []):
                matches[0].attrib.pop(attribute, None)
            matches[0].set("name", symbol)
    if len(matches) != 1:
        available = sorted(node.get("name", "") for node in resources)
        raise ValueError(
            f"RESOURCE_SYMBOL_MISMATCH: {symbol!r} no te exactament un recurs; "
            f"disponibles={available}"
        )


def _split_dates(start: date, end: date, split: dict) -> dict[str, str]:
    if end <= start:
        raise ValueError("date_to ha de ser posterior a date_from")
    days = (end - start).days
    train_end = start + timedelta(days=round(days * split["train_pct"] / 100))
    validation_end = train_end + timedelta(days=round(days * split["validation_pct"] / 100))
    oos_end = validation_end + timedelta(days=round(days * split["oos_pct"] / 100))
    return {"train_from": start.isoformat(), "train_to": train_end.isoformat(),
            "validation_from": (train_end + timedelta(days=1)).isoformat(),
            "validation_to": validation_end.isoformat(),
            "oos_from": (validation_end + timedelta(days=1)).isoformat(),
            "oos_to": oos_end.isoformat(), "holdout_from": (oos_end + timedelta(days=1)).isoformat(),
            "holdout_to": end.isoformat()}


def _validated_v4_periods(contract_path: Path | None, expected_digest: str,
                          methodology_path: Path, date_from: date,
                          date_to: date) -> tuple[dict[str, str], dict]:
    if contract_path is None or not contract_path.is_file():
        raise ValueError("V4_SQ_PERIOD_CONTRACT_REQUIRED")
    contract = json.loads(contract_path.read_text())
    if (temporal_contract_digest(contract) != expected_digest
            or contract.get("methodology_sha256") != _sha256(methodology_path.read_bytes())
            or contract.get("source_first") != date_from.isoformat()
            or contract.get("source_last") != date_to.isoformat()):
        raise ValueError("V4_SQ_PERIOD_CONTRACT_MISMATCH")
    return sq_periods(contract), {
        "temporal_split_contract_path": str(contract_path.resolve()),
        "temporal_split_contract_sha256": expected_digest,
        "temporal_source_sha256": contract["source_sha256"],
        "temporal_split_policy": contract["rounding"],
    }


def _condition(column: str, fmt: str, threshold: float) -> ET.Element:
    xml = f'''<Condition use="true"><Left-Side valueType="column"><Column-Value
      column="{column}" columnType="0" format="{fmt}" resultType="main" direction="0"
      sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30"
      pctRatio="0" class="{column}" /></Left-Side><Comparator value="&gt;" />
      <Right-Side valueType="numeric"><Numeric-Value value="{threshold}" /></Right-Side></Condition>'''
    return ET.fromstring(xml)


def _configure_build(xml: bytes, market: dict, periods: dict, methodology: dict,
                     accepted_limit: int, search_profile: str = "generic_translatable",
                     generation_type: str = "random-generation",
                     attempt_budget: int | None = None,
                     wall_time_minutes: int = 0,
                     market_side: str = "both") -> tuple[bytes, dict]:
    root = ET.fromstring(xml)
    for key in ("ExitAtEndOfDay", "ExitOnFriday"):
        option = root.find(f".//Param[@key='{key}']")
        if option is None:
            raise ValueError(f"Opcio SQ absent: {key}")
        option.text = "false"
    strategy = root.find("./WhatToBuild/StrategyType")
    if strategy is None:
        raise ValueError("StrategyType absent")
    strategy.attrib.update({"type": "simple", "additionalCharts": "0",
                            "templateFile": "SQ3StrategyTemplateExample.sq4", "architecture": "sq4"})
    strategy.attrib.pop("improveDatabank", None)

    complexity = root.find("./WhatToBuild/RulesComplexity")
    if complexity is None:
        raise ValueError("RulesComplexity absent")
    complexity.clear()
    complexity.set("useDifferentSettings", "false")
    is_stop_channel_profile = search_profile in {
        "xau_h4_stop_channel_breakout_v2", "xau_h4_atr_compression_breakout_v3"
    }
    is_sweep_profile = search_profile == "xau_h4_sweep_reclaim_v4"
    is_channel_profile = search_profile == "xau_h4_channel_breakout_v1" or is_stop_channel_profile
    ET.SubElement(complexity, "Chart", {"name": "Main chart",
        "minConditions": "0" if search_profile == "xau_h4_stop_channel_breakout_v2" else "1",
        "maxConditions": "1" if is_stop_channel_profile else ("2" if search_profile == "xau_h4_channel_breakout_v1" or is_sweep_profile else "3"),
        "minExitConditions": "0", "maxExitConditions": "0" if (
            is_channel_profile or search_profile == "generic_translatable") else "1",
        "minExitTypes": "1", "maxExitTypes": "2",
        "minPeriod": "10" if is_channel_profile else "5",
        "maxPeriod": "120" if is_channel_profile else "250",
        "minShift": "1", "maxShift": "2" if is_channel_profile else "3"})
    sides = root.find("./WhatToBuild/MarketSides")
    if market_side not in {"long", "short", "both"}:
        raise ValueError(f"MARKET_SIDE_INVALID: {market_side}")
    sides.set("type", market_side)
    symmetric = "true" if market_side == "both" else "false"
    _set_text(root, "./WhatToBuild/MarketSides/EntrySymmetry", symmetric)
    _set_text(root, "./WhatToBuild/MarketSides/ExitSymmetry", symmetric)
    genetic_shape = (_nominal_genetic_shape(attempt_budget)
                     if generation_type == "genetic-evolution" and attempt_budget is not None
                     else None)
    for path, value in {
        "./WhatToBuild/SLPTOptions/SLRequired": "true",
        "./WhatToBuild/SLPTOptions/SLATR": "true",
        "./WhatToBuild/SLPTOptions/MinSLATRMultiple": "1.5",
        "./WhatToBuild/SLPTOptions/MaxSLATRMultiple": "4",
        "./WhatToBuild/SLPTOptions/MinSLATRPeriod": "10",
        "./WhatToBuild/SLPTOptions/MaxSLATRPeriod": "50",
        "./WhatToBuild/SLPTOptions/PTRequired": "false",
        "./WhatToBuild/SLPTOptions/PTATR": "true",
        "./WhatToBuild/BuildMode/PopulationSize": str(
            genetic_shape["population_per_island"] if genetic_shape else 100),
        "./WhatToBuild/BuildMode/MaxGenerations": str(
            genetic_shape["max_generations"] if genetic_shape else 100),
        "./WhatToBuild/BuildMode/Islands": str(
            genetic_shape["islands"] if genetic_shape else 4),
        "./WhatToBuild/BuildMode/EvoInSamplePeriod": "100",
        "./RiskMoneyManagement/MoneyManagement/InitialCapital": "10000",
        "./Rankings/MaxStrategies": accepted_limit,
    }.items():
        _set_text(root, path, value)

    for method in root.findall("./RiskMoneyManagement/MoneyManagement/Method"):
        method.set("use", "true" if method.get("type") == "FixedSize" else "false")
        if method.get("type") == "FixedSize":
            param = method.find("./Params/Param[@key='Size']")
            if param is not None:
                param.text = "1"

    setup = root.find("./Data/Setups/Setup")
    setup.set("dateFrom", periods["train_from"].replace("-", "."))
    setup.set("dateTo", periods["train_to"].replace("-", "."))
    charts = setup.findall("Chart")
    for extra in charts[1:]:
        setup.remove(extra)
    charts[0].set("symbol", market["sq_symbol"])
    charts[0].set("timeframe", market.get("discovery_timeframe", "M15"))
    charts[0].set("spread", "0")
    setup.set("testPrecision", "2")
    setup.set("slippage", str(_sq_discovery_slippage(market, methodology)))
    _require_resource_symbol(root, market["sq_symbol"], market)
    commission_methods = setup.findall("./Commissions/Method")
    if not commission_methods:
        raise ValueError("No hi ha cap metode de comissio al scaffold SQ")
    commission_method = next(
        (method for method in commission_methods if method.get("type") == "None"),
        commission_methods[0],
    )
    for method in commission_methods:
        method.set("use", "true" if method is commission_method else "false")
    if commission_method.get("type") != "None":
        commission = commission_method.find("./Params/Param[@key=\x27Commission\x27]")
        if commission is None:
            raise ValueError("El metode de comissio actiu no te parametre Commission")
        commission.text = "0"

    for parent_path in ("./WhatToBuild/BuildMode/Conditions", "./Rankings/Conditions"):
        parent = root.find(parent_path)
        if parent is None:
            raise ValueError(f"Camp SQ absent: {parent_path}")
        parent.clear()
    discovery_gate = (methodology["hypothesis_screen"]
                      if methodology.get("schema_version", 1) >= 4
                      else methodology["discovery"])
    ranking_conditions = [
        _condition("NumberOfTrades", "Integer", discovery_gate["minimum_trades_train"]),
        _condition("ProfitFactor", "Decimal2", discovery_gate.get("minimum_profit_factor_train", 1.0)),
    ]
    if "minimum_r_expectancy_train" in discovery_gate:
        ranking_conditions.append(_condition("RExpectancy", "Decimal2", discovery_gate["minimum_r_expectancy_train"]))
    root.find("./Rankings/Conditions").extend(ranking_conditions)
    ranking = root.find("./Rankings/FitnessCriteria/Settings/Ranking")
    ranking.set("type", "ReturnDDRatio")
    stop = root.find("./Rankings/StopCondition")
    stop.attrib.update({"type": "databank-full", "passedStrategies": str(accepted_limit),
                        "restartCount": "0", "days": "0",
                        "hours": str(wall_time_minutes // 60),
                        "minutes": str(wall_time_minutes % 60)})
    crosschecks = root.find("./CrossChecks")
    if crosschecks is not None:
        crosschecks.set("use", "false")

    if search_profile not in SEARCH_PROFILES:
        raise ValueError(f"SEARCH_PROFILE_INVALID: {search_profile}")
    allowed_blocks = SEARCH_PROFILES[search_profile]
    build_mode = root.find("./WhatToBuild/BuildMode")
    if generation_type not in {"random-generation", "genetic-evolution"}:
        raise ValueError(f"GENERATION_TYPE_INVALID: {generation_type}")
    build_mode.set("generationType", generation_type)
    if genetic_shape is not None:
        _set_text(root, "./WhatToBuild/BuildMode/DecimationCoef", "1")
        for path in ("./WhatToBuild/BuildMode/EvoRestartOnFinish",
                     "./WhatToBuild/BuildMode/EvoRestartOnStagnation"):
            node = root.find(path)
            if node is None:
                raise ValueError(f"Camp SQ absent: {path}")
            node.set("status", "false")
    counts = {"enabled": 0, "disabled": 0}
    for block in root.findall(".//Block"):
        enabled = block.get("key") in allowed_blocks
        block.set("use", str(enabled).lower())
        counts["enabled" if enabled else "disabled"] += 1
    if search_profile == "generic_translatable" and counts["enabled"] < 10:
        raise ValueError("No s'han pogut habilitar prou blocs traduibles")
    if search_profile != "generic_translatable" and counts["enabled"] != len(allowed_blocks):
        raise ValueError(
            f"SEARCH_PROFILE_BLOCK_MISMATCH: expected={len(allowed_blocks)} enabled={counts['enabled']}"
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=False), counts


def build(source: Path, output: Path, project_name: str, market_key: str,
          registry_path: Path, methodology_path: Path, date_from: date, date_to: date,
          accepted_limit: int, search_profile: str = "generic_translatable",
          generation_type: str = "random-generation", attempt_budget: int | None = None,
          wall_time_minutes: int = 0, stagnation_attempts: int | None = None,
          market_side: str = "both", evidence_chain_path: Path | None = None,
          campaign_id: str | None = None, source_hypothesis_id: str | None = None,
          period_contract_path: Path | None = None) -> dict:
    methodology = json.loads(methodology_path.read_text())
    errors = validate(methodology)
    if errors:
        raise ValueError("Metodologia invalida: " + "; ".join(errors))
    _validate_generation_contract(methodology, generation_type, attempt_budget)
    prerequisites = _validate_v4_prerequisites(
        methodology, methodology_path, evidence_chain_path, campaign_id,
        source_hypothesis_id, market_key)
    expected_temporal_digest = prerequisites.pop(
        "_expected_temporal_contract_sha256", None)
    if prerequisites:
        snapshot_value = prerequisites.pop("_prerequisite_chain_snapshot")
        snapshot_path = output.with_suffix(".prerequisites.json")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot_value, indent=2, sort_keys=True) + "\n")
        prerequisites["evidence_chain_path"] = str(snapshot_path.resolve())
        prerequisites["evidence_chain_sha256"] = _sha256(snapshot_path.read_bytes())
    registry = json.loads(registry_path.read_text())
    market = registry["markets"].get(market_key)
    if not market or not market.get("research_eligible"):
        raise ValueError(f"Mercat no autoritzat per recerca: {market_key}")
    periods = _split_dates(date_from, date_to, methodology["temporal_split"])
    period_evidence = {}
    if expected_temporal_digest is not None:
        expected_profile = V4_HYPOTHESIS_SEARCH_PROFILES[source_hypothesis_id]
        if search_profile != expected_profile:
            raise ValueError(
                f"V4_SQ_PROFILE_MISMATCH expected={expected_profile} got={search_profile}")
        periods, period_evidence = _validated_v4_periods(
            period_contract_path, expected_temporal_digest,
            methodology_path, date_from, date_to)
    with zipfile.ZipFile(source) as src:
        config = ET.fromstring(src.read("config.xml"))
        build_tasks = [task for task in config.findall("./Tasks/Task") if task.get("type") == "Build"]
        if len(build_tasks) != 1:
            raise ValueError("El scaffold ha de contenir exactament un Build task")
        for task in list(config.find("./Tasks")):
            if task is not build_tasks[0]:
                config.find("./Tasks").remove(task)
        config.set("name", project_name)
        task_file = build_tasks[0].get("taskXMLFile")
        build_xml, block_counts = _configure_build(src.read(task_file), market, periods,
                                                    methodology, accepted_limit, search_profile,
                                                    generation_type, attempt_budget,
                                                    wall_time_minutes, market_side)
    config_xml = ET.tostring(config, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_reproducible_cfx(output, {"config.xml": config_xml, task_file: build_xml})
    payload = output.read_bytes()
    manifest = {"schema_version": 1, "build_reproducible": True,
        "project_name": project_name, "market": market_key, "methodology_id": methodology["methodology_id"],
        "sq_symbol": market["sq_symbol"], "timeframe": market.get("discovery_timeframe", "M15"),
        "methodology_sha256": _sha256(methodology_path.read_bytes()), "source_role": "xml_format_scaffold_only",
        "source_sha256": _sha256(source.read_bytes()), "output_sha256": _sha256(payload),
        "accepted_limit": accepted_limit, "discovery_initial_capital": 10000,
        "sq_discovery_spread": 0,
        "sq_discovery_commission": 0,
        "sq_discovery_slippage": _sq_discovery_slippage(market, methodology),
        "venue_cost_application_stage": "post_sq_frozen_cost_model"
            if methodology.get("schema_version", 1) >= 4 else "legacy_embedded_or_posthoc",
        "search_profile": search_profile, "generation_type": generation_type,
        "market_side": market_side,
        "attempt_budget": attempt_budget, "wall_time_budget_minutes": wall_time_minutes,
        "stagnation_attempts": stagnation_attempts,
        "sq_genetic_shape": (_nominal_genetic_shape(attempt_budget)
                             if generation_type == "genetic-evolution"
                             and attempt_budget is not None else None),
        "canonical_evaluation_capital": methodology["capital_usdc"], "periods": periods,
        "blocks": block_counts, "holdout_sealed": True}
    manifest.update(prerequisites)
    manifest.update(period_evidence)
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--market", required=True)
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("ostium_markets.json"))
    parser.add_argument("--methodology", type=Path, default=Path(__file__).with_name("methodology_v1.json"))
    parser.add_argument("--date-from", type=date.fromisoformat, required=True)
    parser.add_argument("--date-to", type=date.fromisoformat, required=True)
    parser.add_argument("--accepted-limit", type=int, default=100)
    parser.add_argument("--search-profile", choices=SEARCH_PROFILES, default="generic_translatable")
    parser.add_argument("--generation-type", choices=("random-generation", "genetic-evolution"),
                        default="random-generation")
    parser.add_argument("--attempt-budget", type=int)
    parser.add_argument("--wall-time-minutes", type=int, default=0)
    parser.add_argument("--market-side", choices=("long", "short", "both"), default="both")
    parser.add_argument("--stagnation-attempts", type=int)
    parser.add_argument("--evidence-chain", type=Path)
    parser.add_argument("--campaign-id")
    parser.add_argument("--source-hypothesis-id")
    parser.add_argument("--period-contract", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.name, args.market, args.registry,
        args.methodology, args.date_from, args.date_to, args.accepted_limit,
        args.search_profile, args.generation_type, args.attempt_budget,
        args.wall_time_minutes, args.stagnation_attempts, args.market_side,
        args.evidence_chain, args.campaign_id, args.source_hypothesis_id,
        args.period_contract), indent=2))

if __name__ == "__main__":
    main()
