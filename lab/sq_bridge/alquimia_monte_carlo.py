#!/usr/bin/env python3
"""Enable an auditable parameter-only Monte Carlo cross-check in a Retest CFX."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.alquimia_retest import verify_retest_project


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_reproducible(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            archive.writestr(info, files[name])


def _configured_task(files: dict[str, bytes]) -> tuple[ET.Element, str, ET.Element]:
    config = ET.fromstring(files["config.xml"])
    tasks = [task.get("taskXMLFile") for task in config.findall("./Tasks/Task")
             if task.get("type") == "Retest"]
    if len(tasks) != 1 or not tasks[0] or tasks[0] not in files:
        raise ValueError("MONTE_CARLO_RETEST_TASK_INVALID")
    return config, tasks[0], ET.fromstring(files[tasks[0]])


def verify(cfx: Path, manifest: dict, *, source: Path | None = None) -> dict:
    """Reopen the CFX; never trust the generator's summary alone."""
    if (manifest.get("schema_version") != 2
            or manifest.get("cfx_sha256") != _sha(cfx)
            or manifest.get("crosschecks_enabled") is not True
            or manifest.get("method") != "RandomizeStrategyParameters"
            or manifest.get("build_reproducible") is not True):
        raise ValueError("MONTE_CARLO_MANIFEST_INVALID")
    if source is not None and (not source.is_file()
            or manifest.get("source_cfx_sha256") != _sha(source)):
        raise ValueError("MONTE_CARLO_SOURCE_INVALID")
    with zipfile.ZipFile(cfx) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    config, _, root = _configured_task(files)
    crosschecks = root.find("./CrossChecks")
    monte_carlo = root.find("./CrossChecks/MonteCarloRetest")
    enabled = ([node for node in list(crosschecks)
                if node.get("use") == "true"] if crosschecks is not None else [])
    methods = (monte_carlo.findall("./Settings/Methods/Method")
               if monte_carlo is not None else [])
    active_methods = [node for node in methods if node.get("use") == "true"]
    randomized = next((node for node in methods
                       if node.get("type") == "RandomizeStrategyParameters"), None)
    params = ({node.get("key"): node.text
               for node in randomized.findall("./Params/Param")}
              if randomized is not None else {})
    try:
        simulations = int(monte_carlo.findtext("./Settings/NumberOfSimulations", ""))
        probability = int(params["Probability"])
        max_change = int(params["MaxChange"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("MONTE_CARLO_SETTINGS_INVALID") from exc
    if (config.get("name") != manifest.get("project_name")
            or crosschecks is None or crosschecks.get("use") != "true"
            or crosschecks.get("evaluateAll") != "true"
            or enabled != [monte_carlo]
            or active_methods != [randomized]
            or params.get("Symmetric") != "true"
            or simulations != manifest.get("simulations")
            or probability != manifest.get("probability_pct")
            or max_change != manifest.get("max_change_pct")):
        raise ValueError("MONTE_CARLO_CFX_CONTRACT_INVALID")
    return {"project_name": config.get("name"), "simulations": simulations,
            "probability_pct": probability, "max_change_pct": max_change,
            "method": randomized.get("type")}


def verify_project(cfx: Path, manifest: dict, *,
                   require_archive_hash: bool = True) -> dict:
    """Verify an MC CFX plus its immutable pre-holdout candidate lineage."""
    if (manifest.get("stage") != "robustness_parameter_monte_carlo"
            or manifest.get("holdout_accessed") is not False
            or manifest.get("performance_filters_applied_in_sq") is not False):
        raise ValueError("MONTE_CARLO_PROJECT_MANIFEST_INVALID")
    source = Path(manifest.get("source_cfx_path", ""))
    base_manifest_path = Path(manifest.get("base_retest_manifest_path", ""))
    if (not source.is_file() or not base_manifest_path.is_file()
            or manifest.get("source_cfx_sha256") != _sha(source)
            or manifest.get("base_retest_manifest_sha256") != _sha(base_manifest_path)):
        raise ValueError("MONTE_CARLO_PROJECT_LINEAGE_INVALID")
    base = json.loads(base_manifest_path.read_text())
    base_contract = verify_retest_project(source, base)
    if any(manifest.get(key) != base.get(key) for key in (
            "candidate_id", "candidate_sqx_path", "candidate_sqx_sha256",
            "candidate_strategy_xml_sha256")):
        raise ValueError("MONTE_CARLO_PROJECT_CANDIDATE_INVALID")
    checked_manifest = manifest if require_archive_hash else {
        **manifest, "cfx_sha256": _sha(cfx)}
    settings = verify(cfx, checked_manifest, source=source)
    return {"project_name": settings["project_name"],
            "candidate_id": base_contract["candidate_id"], **settings}


def generate(source: Path, output: Path, project_name: str, simulations: int,
             probability_pct: int = 10, max_change_pct: int = 10,
             base_retest_manifest_path: Path | None = None) -> dict:
    if simulations < 50:
        raise ValueError("MONTE_CARLO_SIMULATIONS_TOO_LOW")
    if not 1 <= probability_pct <= 100 or not 1 <= max_change_pct <= 100:
        raise ValueError("MONTE_CARLO_PARAMETER_RANGE_INVALID")
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    config, task_name, root = _configured_task(files)
    config.set("name", project_name)
    crosschecks = root.find("./CrossChecks")
    monte_carlo = root.find("./CrossChecks/MonteCarloRetest")
    if crosschecks is None or monte_carlo is None:
        raise ValueError("MONTE_CARLO_STRUCTURE_MISSING")
    crosschecks.set("use", "true")
    crosschecks.set("evaluateAll", "true")
    for crosscheck in list(crosschecks):
        if "use" in crosscheck.attrib:
            crosscheck.set("use", "false")
    for method in monte_carlo.findall("./Settings/Methods/Method"):
        enabled = method.get("type") == "RandomizeStrategyParameters"
        method.set("use", str(enabled).lower())
        if enabled:
            params = {node.get("key"): node for node in method.findall("./Params/Param")}
            params["Probability"].text = str(probability_pct)
            params["MaxChange"].text = str(max_change_pct)
            params["Symmetric"].text = "true"
    # Set this after disabling sibling cross-checks: MonteCarloRetest itself is
    # one of the children iterated above.
    monte_carlo.set("use", "true")
    monte_carlo.find("./Settings/NumberOfSimulations").text = str(simulations)
    delete_failed = root.find("./Rankings/DeleteFailedStrategies")
    if delete_failed is not None:
        delete_failed.text = "false"
    files["config.xml"] = ET.tostring(config, encoding="utf-8")
    files[task_name] = ET.tostring(root, encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_reproducible(output, files)
    result = {
        "schema_version": 2,
        "project_name": project_name,
        "source_cfx_sha256": _sha(source),
        "cfx_sha256": _sha(output),
        "build_reproducible": True,
        "crosschecks_enabled": True,
        "method": "RandomizeStrategyParameters",
        "simulations": simulations,
        "probability_pct": probability_pct,
        "max_change_pct": max_change_pct,
    }
    if base_retest_manifest_path is not None:
        base_retest_manifest_path = base_retest_manifest_path.resolve()
        base = json.loads(base_retest_manifest_path.read_text())
        verify_retest_project(source, base)
        result.update({
            "stage": "robustness_parameter_monte_carlo",
            "source_cfx_path": str(source.resolve()),
            "base_retest_manifest_path": str(base_retest_manifest_path),
            "base_retest_manifest_sha256": _sha(base_retest_manifest_path),
            "candidate_id": base["candidate_id"],
            "candidate_sqx_path": base["candidate_sqx_path"],
            "candidate_sqx_sha256": base["candidate_sqx_sha256"],
            "candidate_strategy_xml_sha256": base["candidate_strategy_xml_sha256"],
            "holdout_accessed": False,
            "performance_filters_applied_in_sq": False,
        })
    verify(output, result, source=source)
    if base_retest_manifest_path is not None:
        verify_project(output, result)
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
    parser.add_argument("--base-retest-manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.output, args.name, args.simulations,
                              args.probability_pct, args.max_change_pct,
                              args.base_retest_manifest), indent=2))


if __name__ == "__main__":
    main()
