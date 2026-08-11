#!/usr/bin/env python3
"""Structural verification of a frozen StrategyQuant genetic project."""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from lab.sq_bridge.eurusd_v4_hypotheses import EURUSD_PROFILE_BLOCKS


EURUSD_V4_PROFILE_BLOCKS = EURUSD_PROFILE_BLOCKS


def _positive_int(text: str | None, label: str) -> int:
    try:
        value = int(text or "")
    except ValueError as exc:
        raise ValueError(f"SQ_CFX_INVALID_{label}") from exc
    if value < 1:
        raise ValueError(f"SQ_CFX_INVALID_{label}")
    return value


def verify_genetic_project(path: Path, manifest: dict) -> dict[str, int]:
    """Reopen a CFX and prove its nominal genetic shape matches the manifest."""
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if names.count("config.xml") != 1 or len(names) != len(set(names)):
                raise ValueError("SQ_CFX_AMBIGUOUS_ARCHIVE")
            config = ET.fromstring(archive.read("config.xml"))
            tasks = [node for node in config.findall("./Tasks/Task")
                     if node.get("type") == "Build"]
            if len(tasks) != 1 or len(config.findall("./Tasks/Task")) != 1:
                raise ValueError("SQ_CFX_REQUIRES_ONE_BUILD_TASK")
            task_name = tasks[0].get("taskXMLFile")
            if (not task_name or task_name.startswith(("/", "\\")) or ".." in Path(task_name).parts
                    or names.count(task_name) != 1):
                raise ValueError("SQ_CFX_INVALID_TASK_PATH")
            root = ET.fromstring(archive.read(task_name))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        raise ValueError("SQ_CFX_UNREADABLE") from exc

    mode = root.find("./WhatToBuild/BuildMode")
    if mode is None or mode.get("generationType") != "genetic-evolution":
        raise ValueError("SQ_CFX_NOT_GENETIC")
    population = _positive_int(mode.findtext("PopulationSize"), "POPULATION")
    generations = _positive_int(mode.findtext("MaxGenerations"), "GENERATIONS")
    islands = _positive_int(mode.findtext("Islands"), "ISLANDS")
    decimation = _positive_int(mode.findtext("DecimationCoef"), "DECIMATION")
    if decimation != 1:
        raise ValueError("SQ_CFX_DECIMATION_NOT_ONE")
    for name in ("EvoRestartOnFinish", "EvoRestartOnStagnation"):
        node = mode.find(name)
        if node is None or node.get("status") != "false":
            raise ValueError(f"SQ_CFX_{name.upper()}_ENABLED")

    nominal = islands * population * generations
    shape = {"islands": islands, "population_per_island": population,
             "max_generations": generations, "nominal_evaluations": nominal}
    budget = manifest.get("attempt_budget")
    guard = manifest.get("attempt_stop_guard")
    if (not isinstance(budget, int) or isinstance(budget, bool) or nominal > budget
            or not isinstance(guard, int) or isinstance(guard, bool)
            or not 0 <= guard < budget or manifest.get("sq_genetic_shape") != shape):
        raise ValueError("SQ_CFX_GENETIC_BUDGET_MISMATCH")

    setup = root.find("./Data/Setups/Setup")
    charts = setup.findall("./Chart") if setup is not None else []
    periods = manifest.get("periods")
    if (setup is None or len(charts) != 1 or not isinstance(periods, dict)
            or setup.get("dateFrom") != str(periods.get("train_from", "")).replace("-", ".")
            or setup.get("dateTo") != str(periods.get("train_to", "")).replace("-", ".")
            or charts[0].get("symbol") != manifest.get("sq_symbol")
            or charts[0].get("timeframe") != manifest.get("timeframe")
            or charts[0].get("spread") != "0"
            or setup.get("slippage") != "0"):
        raise ValueError("SQ_CFX_TRAIN_DATA_OR_ZERO_COST_CONTRACT_MISMATCH")
    commission = [row for row in setup.findall("./Commissions/Method")
                  if row.get("use") == "true"]
    if len(commission) != 1 or commission[0].get("type") != "None":
        raise ValueError("SQ_CFX_COMMISSION_NOT_DISABLED")
    sides = root.find("./WhatToBuild/MarketSides")
    expected_side = manifest.get("market_side")
    expected_symmetry = "true" if expected_side == "both" else "false"
    if (expected_side not in {"long", "short", "both"} or sides is None
            or sides.get("type") != expected_side
            or sides.findtext("EntrySymmetry") != expected_symmetry
            or sides.findtext("ExitSymmetry") != expected_symmetry):
        raise ValueError("SQ_CFX_MARKET_SIDE_MISMATCH")
    capital = root.findtext("./RiskMoneyManagement/MoneyManagement/InitialCapital")
    methods = root.findall("./RiskMoneyManagement/MoneyManagement/Method")
    fixed = [row for row in methods if row.get("use") == "true"]
    fixed_size = (fixed[0].find("./Params/Param[@key='Size']")
                  if len(fixed) == 1 else None)
    if (capital != str(manifest.get("discovery_initial_capital"))
            or len(fixed) != 1 or fixed[0].get("type") != "FixedSize"
            or fixed_size is None or fixed_size.text != "1"):
        raise ValueError("SQ_CFX_DISCOVERY_SIZING_MISMATCH")
    ranking = root.find("./Rankings/FitnessCriteria/Settings/Ranking")
    crosschecks = root.find("./CrossChecks")
    if (ranking is None or ranking.get("type") != "ReturnDDRatio"
            or (crosschecks is not None and crosschecks.get("use") != "false")):
        raise ValueError("SQ_CFX_FITNESS_OR_CROSSCHECK_CONTRACT_MISMATCH")
    sl_required = root.findtext("./WhatToBuild/SLPTOptions/SLRequired")
    if sl_required != "true":
        raise ValueError("SQ_CFX_STOP_LOSS_NOT_REQUIRED")

    stop = root.find("./Rankings/StopCondition")
    accepted = manifest.get("accepted_limit")
    wall_minutes = manifest.get("wall_time_budget_minutes")
    if (stop is None or stop.get("type") != "databank-full"
            or stop.get("passedStrategies") != str(accepted)
            or stop.get("restartCount") != "0"
            or not isinstance(wall_minutes, int) or isinstance(wall_minutes, bool)
            or stop.get("hours") != str(wall_minutes // 60)
            or stop.get("minutes") != str(wall_minutes % 60)):
        raise ValueError("SQ_CFX_STOP_CONDITION_MISMATCH")
    profile = manifest.get("search_profile")
    search_space = (manifest.get("blocks") or {}).get("search_space")
    genetic = (manifest.get("blocks") or {}).get("genetic_parameters")
    if isinstance(search_space, dict):
        expected_genetic = {
            "CrossoverProbability": "crossover_probability_pct",
            "MutationProbability": "mutation_probability_pct",
            "MigrationModulo": "migration_every_generations",
            "MigrationRate": "migration_rate_pct",
            "InitGenerationType": "initial_population_mode",
        }
        if (profile not in EURUSD_V4_PROFILE_BLOCKS or not isinstance(genetic, dict)
                or any(mode.findtext(xml_name) != str(genetic.get(contract_name))
                       for xml_name, contract_name in expected_genetic.items())):
            raise ValueError("SQ_CFX_GENETIC_PARAMETERS_MISMATCH")
        complexity = root.find("./WhatToBuild/RulesComplexity/Chart")
        expected_complexity = {
            "minPeriod": "indicator_period_min", "maxPeriod": "indicator_period_max",
            "minShift": "shift_min", "maxShift": "shift_max",
        }
        if (complexity is None
                or any(complexity.get(attribute) != str(search_space.get(contract_key))
                       for attribute, contract_key in expected_complexity.items())):
            raise ValueError("SQ_CFX_SEARCH_RANGE_MISMATCH")
        enabled_rows = [row for row in root.findall(".//Block")
                        if row.get("use") == "true"]
        blocks = {row.get("key"): row for row in enabled_rows}
        enabled = set(blocks)
        if len(blocks) != len(enabled_rows):
            raise ValueError("SQ_CFX_DUPLICATE_ENABLED_BLOCKS")
        if enabled != EURUSD_V4_PROFILE_BLOCKS[profile]:
            raise ValueError("SQ_CFX_ENABLED_BLOCKS_MISMATCH")
        for key in enabled:
            block = blocks[key]
            if (block.get("weight") != "1"
                    or any(list(row) for row in block.findall(".//Predefined"))
                    or any(param.get("generation") != "fixed"
                           or param.get("defaultValue") != "0"
                           for param in block.findall(
                               ".//Generated/Param[@key='#ComputedFrom#']"))):
                raise ValueError("SQ_CFX_INHERITED_BLOCK_CONFIGURATION")
            if block.get("category") == "exitTypes" and block.get("probability") != "100":
                raise ValueError("SQ_CFX_EXIT_PROBABILITY_MISMATCH")
        exit_param = blocks["ExitAfterBars.ExitAfterBars"].find(
            ".//Generated/Param[@key='#ExitAfterBars#']")
        if (exit_param is None
                or exit_param.get("minValue") != str(search_space["exit_after_bars_min"])
                or exit_param.get("maxValue") != str(search_space["exit_after_bars_max"])
                or exit_param.get("step") != str(search_space["exit_after_bars_step"])):
            raise ValueError("SQ_CFX_EXIT_RANGE_MISMATCH")
        for key, prefix in (("Indicators.RSI", "rsi_threshold"),
                            ("Indicators.ROC", "roc_threshold")):
            if key not in enabled:
                continue
            block = blocks[key]
            if any(block.get(attribute) != str(search_space[f"{prefix}_{suffix}"])
                   for attribute, suffix in (("indicatorMin", "min"),
                                             ("indicatorMax", "max"),
                                             ("indicatorStep", "step"))):
                raise ValueError("SQ_CFX_INDICATOR_THRESHOLD_MISMATCH")
    return shape
