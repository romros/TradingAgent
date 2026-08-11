#!/usr/bin/env python3
"""Resume EURUSD v4 screen branches through supervised SQ generation."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from lab.sq_bridge.alquimia_project import SEARCH_PROFILES
from lab.sq_bridge.eurusd_v4_project_batch import compile_projects
from lab.sq_bridge.eurusd_v4_screen_trigger import (
    _copy_atomic, verify_completed as verify_screen,
)
from lab.sq_bridge.sq_generation_stage_v4 import run_stage
from lab.sq_bridge.sq_generation_universe_v4 import build_universe
from lab.sq_bridge.sqcli_import_batch import import_batch
from lab.sq_bridge.sqcli_transport import list_projects_with_status
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _resolve(config_path: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("worker config path missing")
    path = Path(value)
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def validate_scaffold(path: Path, expected_hash: str,
                      expected_version: str) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file() or _sha(path) != expected_hash:
        raise ValueError("technical scaffold path/hash mismatch")
    try:
        with zipfile.ZipFile(path) as archive:
            config = ET.fromstring(archive.read("config.xml"))
            build_tasks = [row for row in config.findall("./Tasks/Task")
                           if row.get("type") == "Build"]
            if len(build_tasks) != 1 or config.get("version") != expected_version:
                raise ValueError("technical scaffold SQ version/task mismatch")
            task_name = build_tasks[0].get("taskXMLFile")
            build = ET.fromstring(archive.read(str(task_name)))
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as error:
        raise ValueError("technical scaffold archive invalid") from error
    required_paths = (
        "./WhatToBuild/StrategyType", "./WhatToBuild/RulesComplexity",
        "./WhatToBuild/MarketSides", "./WhatToBuild/BuildMode",
        "./WhatToBuild/SLPTOptions", "./RiskMoneyManagement/MoneyManagement",
        "./Data/Setups/Setup", "./Rankings/Conditions",
        "./Rankings/FitnessCriteria/Settings/Ranking", "./Rankings/StopCondition",
    )
    missing = [value for value in required_paths if build.find(value) is None]
    available = {row.get("key") for row in build.findall(".//Block")}
    required_blocks = set().union(*(
        SEARCH_PROFILES[name] for name in (
            "eurusd_d1_breakout_v4", "eurusd_d1_momentum_v4",
            "eurusd_d1_shock_reversion_v4")))
    if missing or not required_blocks.issubset(available):
        raise ValueError("technical scaffold lacks required SQ fields/blocks")
    return {
        "sq_version": expected_version, "build_task_file": task_name,
        "available_block_count": len(available),
        "required_block_count": len(required_blocks),
        "source_role": "xml_format_only_no_strategy_or_performance_reuse",
    }


def _running(rows: list[dict]) -> list[str]:
    return sorted(str(row.get("projectName")) for row in rows
                  if row.get("runningStatus") not in {None, 0})


def _waiting(decision: str, campaign_id: object, **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": 1, "decision": decision,
        "campaign_id": campaign_id, **extra,
        "paper_authorized": False, "live_authorized": False,
    }


def tick(
    *, screen_dir: Path, config_path: Path, output_dir: Path,
    projects_root: Path = Path("/mnt/volume-SQ/user/projects"),
    disk_path: Path = Path("/mnt/volume-SQ"),
    listing_fn: Callable[..., list[dict]] = list_projects_with_status,
    compile_fn: Callable[..., dict] = compile_projects,
    import_fn: Callable[..., dict] = import_batch,
    run_fn: Callable[..., dict] = run_stage,
    universe_fn: Callable[..., dict] = build_universe,
    screen_verify_fn: Callable[[Path], dict] = verify_screen,
    scaffold_validate_fn: Callable[..., dict] = validate_scaffold,
) -> dict[str, Any]:
    """Make one durable worker pass; a generation call may run for hours."""
    screen_dir, config_path, output_dir = (
        path.resolve() for path in (screen_dir, config_path, output_dir))
    if not (screen_dir / "screen_trigger_receipt.json").is_file():
        return _waiting("WAITING_FOR_SCREEN", None, sqcli_started=False)
    screen = screen_verify_fn(screen_dir)
    if screen.get("decision") == "REJECT_SCREEN_TRIGGER":
        return _waiting("REJECT_NO_SCREEN_HYPOTHESIS", screen.get("campaign_id"),
                        sqcli_started=False, selected_hypothesis_ids=[])
    if screen.get("decision") != "PASS_SCREEN_TRIGGER":
        raise ValueError("screen trigger has an unsupported decision")

    config = _load(config_path)
    campaign_id = screen.get("campaign_id")
    if (config.get("schema_version") != 1
            or config.get("campaign_id") != campaign_id
            or config.get("auto_import") is not True
            or config.get("auto_start_generation") is not True
            or config.get("paper_authorized") is not False
            or config.get("live_authorized") is not False):
        raise ValueError("SQ worker configuration invalid")
    scaffold_source = _resolve(config_path, config.get("scaffold_path"))
    registry_source = _resolve(config_path, config.get("registry_path"))
    scaffold_contract = scaffold_validate_fn(
        scaffold_source, config.get("scaffold_sha256"),
        config.get("scaffold_sq_version"))
    if not registry_source.is_file() or _sha(registry_source) != config.get("registry_sha256"):
        raise ValueError("SQ worker registry path/hash mismatch")
    methodology_source = Path(str(screen.get("methodology_path", ""))).resolve()
    if (not methodology_source.is_file()
            or _sha(methodology_source) != screen.get("methodology_sha256")):
        raise ValueError("SQ worker frozen methodology mismatch")

    journal_path = output_dir / "worker_journal.json"
    final_path = output_dir / "worker_receipt.json"
    if final_path.is_file():
        result = _load(final_path)
        if (result.get("decision") not in {
                "PASS_SQ_GENERATION_ORCHESTRATED", "REJECT_NO_SQ_CANDIDATES"}
                or result.get("campaign_id") != campaign_id):
            raise ValueError("completed worker receipt invalid")
        for row in (result.get("generation_artifacts") or {}).values():
            path = Path(str(row.get("path", "")))
            if not path.is_file() or _sha(path) != row.get("sha256"):
                raise ValueError("completed generation artifact changed")
        universe_path = Path(str(result.get("global_generation_artifact_path", "")))
        if (not universe_path.is_file()
                or _sha(universe_path) != result.get("global_generation_artifact_sha256")):
            raise ValueError("completed global generation artifact changed")
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    frozen = output_dir / "frozen"
    snapshot_sources = {
        "scaffold": (scaffold_source, frozen / "sq143_scaffold.cfx",
                     config["scaffold_sha256"]),
        "registry": (registry_source, frozen / "ostium_markets.json",
                     config["registry_sha256"]),
        "methodology": (methodology_source, frozen / "methodology_v4.json",
                        screen["methodology_sha256"]),
    }
    journal_contract = {
        "schema_version": 1, "campaign_id": campaign_id,
        "screen_receipt_path": str((screen_dir / "screen_trigger_receipt.json").resolve()),
        "screen_receipt_sha256": _sha(screen_dir / "screen_trigger_receipt.json"),
        "config_path": str(config_path), "config_sha256": _sha(config_path),
        "sources": {name: {"source_path": str(source),
                            "snapshot_path": str(destination), "sha256": digest}
                    for name, (source, destination, digest) in snapshot_sources.items()},
        "scaffold_contract": scaffold_contract,
        "selected_hypothesis_ids": screen.get("selected_hypothesis_ids"),
        "phase": "PREPARED", "current_hypothesis_id": None,
        "generation_artifacts": {}, "paper_authorized": False,
        "live_authorized": False,
    }
    if journal_path.is_file():
        journal = _load(journal_path)
        for key, value in journal_contract.items():
            if key not in {"phase", "current_hypothesis_id", "generation_artifacts"} \
                    and journal.get(key) != value:
                raise ValueError("SQ worker journal does not match frozen inputs")
    else:
        journal = journal_contract
        write_atomic(journal_path, journal)
    for source, destination, digest in snapshot_sources.values():
        _copy_atomic(source, destination, digest)

    bootstrap_path = Path(str(screen.get("bootstrap_path", ""))).resolve()
    batch_dir = output_dir / "cfx_batch"
    batch = compile_fn(
        bootstrap_path=bootstrap_path,
        scaffold_path=snapshot_sources["scaffold"][1],
        registry_path=snapshot_sources["registry"][1],
        methodology_path=snapshot_sources["methodology"][1],
        output_dir=batch_dir)
    journal["phase"] = "CFX_READY"
    write_atomic(journal_path, journal)

    base_url, container = config["base_url"], config["sqcli_container"]
    running = _running(listing_fn(base_url))
    current = journal.get("current_hypothesis_id")
    projects = batch.get("projects") or {}
    own_running = (isinstance(current, str) and current in projects
                   and running == [projects[current]["project_name"]])
    if running and not own_running:
        return _waiting("WAITING_FOR_SQCLI_IDLE", campaign_id,
                        running_projects=running, sqcli_started=False)

    import_receipt = import_fn(
        batch_path=batch_dir / "project_batch.json",
        output_dir=output_dir / "sqcli_import", base_url=base_url,
        container=container)
    journal["phase"] = "IMPORTED"
    write_atomic(journal_path, journal)

    selected = screen.get("selected_hypothesis_ids")
    if not isinstance(selected, list) or sorted(projects) != sorted(selected):
        raise ValueError("worker batch differs from frozen screen")
    artifacts = journal.get("generation_artifacts") or {}
    for hypothesis_id in sorted(selected):
        if hypothesis_id in artifacts:
            path = Path(artifacts[hypothesis_id]["path"])
            if not path.is_file() or _sha(path) != artifacts[hypothesis_id]["sha256"]:
                raise ValueError(f"completed worker branch changed: {hypothesis_id}")
            continue
        if journal.get("current_hypothesis_id") not in {None, hypothesis_id}:
            raise ValueError("worker journal has an inconsistent active branch")
        if journal.get("current_hypothesis_id") is None:
            busy = _running(listing_fn(base_url))
            if busy:
                return _waiting("WAITING_FOR_SQCLI_IDLE", campaign_id,
                                running_projects=busy, sqcli_started=False)
        journal["phase"] = "RUNNING_GENERATION"
        journal["current_hypothesis_id"] = hypothesis_id
        write_atomic(journal_path, journal)
        artifact_path = output_dir / "runs" / hypothesis_id / "sq_generation.json"
        artifact = run_fn(
            import_receipt_path=output_dir / "sqcli_import" /
                "sqcli_import_receipt.json",
            hypothesis_id=hypothesis_id, campaign_id=campaign_id,
            methodology_path=snapshot_sources["methodology"][1],
            run_dir=output_dir / "runs" / hypothesis_id / "supervisor",
            output_path=artifact_path, projects_root=projects_root,
            disk_path=disk_path, base_url=base_url, container=container)
        if artifact.get("decision") not in {"PASS", "REJECT"}:
            raise RuntimeError("SQ generation returned invalid terminal decision")
        artifacts[hypothesis_id] = {
            "decision": artifact["decision"], "path": str(artifact_path.resolve()),
            "sha256": _sha(artifact_path),
            "candidate_ids": artifact.get("candidate_ids", []),
        }
        journal["generation_artifacts"] = artifacts
        journal["current_hypothesis_id"] = None
        journal["phase"] = "IMPORTED"
        write_atomic(journal_path, journal)

    generation_paths = {
        hypothesis_id: Path(row["path"])
        for hypothesis_id, row in artifacts.items()
    }
    universe_path = output_dir / "global_sq_generation.json"
    universe = universe_fn(
        campaign_id=campaign_id,
        generation_artifact_paths=generation_paths,
        expected_hypothesis_ids=sorted(selected),
        global_candidate_budget=_load(snapshot_sources["methodology"][1])[
            "sq_generation"]["accepted_candidates_global_budget"],
        output_path=universe_path)
    candidates = universe["candidate_ids"]
    result = {
        "schema_version": 1,
        "decision": ("PASS_SQ_GENERATION_ORCHESTRATED" if candidates
                     else "REJECT_NO_SQ_CANDIDATES"),
        "campaign_id": campaign_id, "selected_hypothesis_ids": sorted(selected),
        "generation_artifacts": artifacts, "candidate_ids": candidates,
        "global_generation_artifact_path": str(universe_path.resolve()),
        "global_generation_artifact_sha256": _sha(universe_path),
        "sqcli_import_receipt_path": str((output_dir / "sqcli_import" /
                                           "sqcli_import_receipt.json").resolve()),
        "paper_authorized": False, "live_authorized": False,
    }
    write_atomic(final_path, result)
    journal["phase"] = "COMPLETED"
    journal["worker_receipt_sha256"] = _sha(final_path)
    write_atomic(journal_path, journal)
    return result


def main() -> None:
    root = Path(__file__).parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-dir", type=Path, default=root / "data" /
                        "alquimia_v4/eurusd-d1-alquimia-v4/screen-bootstrap")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).with_name("eurusd_v4_sq_worker_config.json"))
    parser.add_argument("--output-dir", type=Path, default=root / "data" /
                        "alquimia_v4/eurusd-d1-alquimia-v4/sq-worker")
    args = parser.parse_args()
    result = tick(screen_dir=args.screen_dir, config_path=args.config,
                  output_dir=args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
