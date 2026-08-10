#!/usr/bin/env python3
"""Structural verification of a frozen StrategyQuant genetic project."""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


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
    if (not isinstance(budget, int) or isinstance(budget, bool) or nominal > budget
            or manifest.get("sq_genetic_shape") != shape):
        raise ValueError("SQ_CFX_GENETIC_BUDGET_MISMATCH")

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
    return shape
