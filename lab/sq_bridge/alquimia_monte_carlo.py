#!/usr/bin/env python3
"""Enable an auditable parameter-only Monte Carlo cross-check in a Retest CFX."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


def generate(source: Path, output: Path, project_name: str, simulations: int,
             probability_pct: int = 10, max_change_pct: int = 10) -> dict:
    if simulations < 50:
        raise ValueError("MONTE_CARLO_SIMULATIONS_TOO_LOW")
    if not 1 <= probability_pct <= 100 or not 1 <= max_change_pct <= 100:
        raise ValueError("MONTE_CARLO_PARAMETER_RANGE_INVALID")
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    config = ET.fromstring(files["config.xml"])
    config.set("name", project_name)
    task_name = next(task.get("taskXMLFile") for task in config.findall("./Tasks/Task")
                     if task.get("type") == "Retest")
    root = ET.fromstring(files[task_name])
    crosschecks = root.find("./CrossChecks")
    monte_carlo = root.find("./CrossChecks/MonteCarloRetest")
    if crosschecks is None or monte_carlo is None:
        raise ValueError("MONTE_CARLO_STRUCTURE_MISSING")
    crosschecks.set("use", "true")
    crosschecks.set("evaluateAll", "true")
    for crosscheck in list(crosschecks):
        if "use" in crosscheck.attrib:
            crosscheck.set("use", "false")
    monte_carlo.set("use", "true")
    for method in monte_carlo.findall("./Settings/Methods/Method"):
        enabled = method.get("type") == "RandomizeStrategyParameters"
        method.set("use", str(enabled).lower())
        if enabled:
            params = {node.get("key"): node for node in method.findall("./Params/Param")}
            params["Probability"].text = str(probability_pct)
            params["MaxChange"].text = str(max_change_pct)
            params["Symmetric"].text = "true"
    monte_carlo.find("./Settings/NumberOfSimulations").text = str(simulations)
    delete_failed = root.find("./Rankings/DeleteFailedStrategies")
    if delete_failed is not None:
        delete_failed.text = "false"
    files["config.xml"] = ET.tostring(config, encoding="utf-8")
    files[task_name] = ET.tostring(root, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    result = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "source_cfx_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "cfx_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "crosschecks_enabled": True,
        "method": "RandomizeStrategyParameters",
        "simulations": simulations,
        "probability_pct": probability_pct,
        "max_change_pct": max_change_pct,
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--simulations", type=int, default=1000)
    parser.add_argument("--probability-pct", type=int, default=10)
    parser.add_argument("--max-change-pct", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.output, args.name, args.simulations,
                              args.probability_pct, args.max_change_pct), indent=2))


if __name__ == "__main__":
    main()
