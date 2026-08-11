#!/usr/bin/env python3
"""Compile every EURUSD v4 branch from the real SQ scaffold without running SQ."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from lab.sq_bridge.alquimia_project import (
    _configure_build, _nominal_genetic_shape, _write_reproducible_cfx,
)
from lab.sq_bridge.eurusd_v4_hypotheses import EURUSD_PROFILE_BLOCKS
from lab.sq_bridge.eurusd_v4_sq_worker import validate_scaffold
from lab.sq_bridge.sq_project_contract import verify_genetic_project
from lab.sq_bridge.temporal_split_contract_v4 import build_contract, digest, sq_periods


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smoke(*, scaffold_path: Path, source_path: Path, registry_path: Path,
          methodology_path: Path, worker_config_path: Path) -> dict:
    scaffold_path, source_path, registry_path, methodology_path, worker_config_path = (
        path.resolve() for path in (
            scaffold_path, source_path, registry_path, methodology_path,
            worker_config_path))
    methodology = json.loads(methodology_path.read_text())
    market = json.loads(registry_path.read_text())["markets"]["EURUSD"]
    worker_config = json.loads(worker_config_path.read_text())
    if (worker_config.get("schema_version") != 1
            or worker_config.get("scaffold_path") != str(scaffold_path)
            or worker_config.get("registry_sha256") != _sha(registry_path)):
        raise ValueError("worker config does not bind the requested scaffold/registry")
    scaffold_contract = validate_scaffold(
        scaffold_path, worker_config.get("scaffold_sha256"),
        worker_config.get("scaffold_sq_version"))
    contract = build_contract(source_path, methodology_path)
    periods = sq_periods(contract)
    budget = methodology["sq_generation"]["maximum_attempts"]
    guard = methodology["sq_generation"]["attempt_stop_guard"]
    with zipfile.ZipFile(scaffold_path) as archive:
        config_source = archive.read("config.xml")
        config_template = ET.fromstring(config_source)
        build_tasks = [row for row in config_template.findall("./Tasks/Task")
                       if row.get("type") == "Build"]
        if len(build_tasks) != 1:
            raise ValueError("real scaffold must contain exactly one Build task")
        task_name = build_tasks[0].get("taskXMLFile")
        if not task_name:
            raise ValueError("real scaffold Build task has no XML member")
        build_source = archive.read(task_name)

    rows = []
    with tempfile.TemporaryDirectory(prefix="alquimia-eurusd-v4-smoke-") as directory:
        temporary = Path(directory)
        for profile in sorted(EURUSD_PROFILE_BLOCKS):
            for side in ("both", "long", "short"):
                config = ET.fromstring(config_source)
                tasks = config.find("./Tasks")
                builds = [row for row in config.findall("./Tasks/Task")
                          if row.get("type") == "Build"]
                for task in list(tasks):
                    if task is not builds[0]:
                        tasks.remove(task)
                project_name = f"SMOKE_{profile}_{side}"
                config.set("name", project_name)
                build_xml, blocks = _configure_build(
                    build_source, market, periods, methodology,
                    accepted_limit=1, search_profile=profile,
                    generation_type="genetic-evolution", attempt_budget=budget,
                    wall_time_minutes=0, market_side=side)
                cfx = temporary / f"{project_name}.cfx"
                _write_reproducible_cfx(cfx, {
                    "config.xml": ET.tostring(config, encoding="utf-8"),
                    task_name: build_xml,
                })
                manifest = {
                    "attempt_budget": budget, "attempt_stop_guard": guard,
                    "accepted_limit": 1, "wall_time_budget_minutes": 0,
                    "sq_genetic_shape": _nominal_genetic_shape(budget),
                    "search_profile": profile, "blocks": blocks,
                    "periods": periods, "sq_symbol": market["sq_symbol"],
                    "timeframe": market["discovery_timeframe"],
                    "market_side": side, "discovery_initial_capital": 10000,
                }
                shape = verify_genetic_project(cfx, manifest)
                rows.append({
                    "profile": profile, "market_side": side,
                    "cfx_sha256": _sha(cfx), **shape,
                })
    return {
        "schema_version": 1,
        "decision": "PASS_REAL_SCAFFOLD_STRUCTURAL_SMOKE",
        "performance_accessed": False,
        "sqcli_started": False,
        "scaffold_path": str(scaffold_path),
        "scaffold_sha256": _sha(scaffold_path),
        "source_path": str(source_path), "source_sha256": _sha(source_path),
        "registry_path": str(registry_path), "registry_sha256": _sha(registry_path),
        "methodology_path": str(methodology_path),
        "methodology_sha256": _sha(methodology_path),
        "worker_config_path": str(worker_config_path),
        "worker_config_sha256": _sha(worker_config_path),
        "scaffold_contract": scaffold_contract,
        "temporal_contract_sha256": digest(contract),
        "periods": periods, "verified_branch_count": len(rows), "branches": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scaffold", type=Path,
                        default=Path("/mnt/volume-SQ/user/projects/EURUSD/project.cfx"))
    parser.add_argument("--source", type=Path, default=Path(
        "/mnt/volume-SQ/user/imports/alquimia_eurusd_v4/"
        "EURUSD_ALQ_NY17_D1_V3.csv"))
    parser.add_argument("--registry", type=Path,
                        default=Path(__file__).with_name("ostium_markets.json"))
    parser.add_argument("--methodology", type=Path,
                        default=Path(__file__).with_name("methodology_v4.json"))
    parser.add_argument("--worker-config", type=Path, default=Path(__file__).with_name(
        "eurusd_v4_sq_worker_config.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = smoke(
        scaffold_path=args.scaffold, source_path=args.source,
        registry_path=args.registry, methodology_path=args.methodology,
        worker_config_path=args.worker_config)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
