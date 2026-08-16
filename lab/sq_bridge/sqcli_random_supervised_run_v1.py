#!/usr/bin/env python3
"""Import, verify, start and supervise one frozen random-generation SQ project."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from functools import partial
from pathlib import Path

from lab.sq_bridge.sq_random_project_contract_v1 import verify
from lab.sq_bridge.sq_watchdog import gui_snapshot, load_limits, run_monitor, write_atomic
from lab.sq_bridge.sqcli_transport import (
    docker_project_final_stats,
    gui_confirm_existing_project_resources,
    gui_open_project,
    gui_project_action_from_cli,
    gui_start_project,
    list_projects_with_status,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    shape = verify(args.project, manifest)
    name = manifest["project_name"]
    listing = {row["projectName"]: row for row in list_projects_with_status(args.base_url)}
    if any(row.get("runningStatus") not in (0, 4, 50) for row in listing.values()):
        raise RuntimeError("another SQ project is active")
    if name not in listing:
        staged = f"/tmp/alquimia-import-{digest(args.project)[:16]}.cfx"
        subprocess.run(["docker", "cp", str(args.project), f"{args.container}:{staged}"], check=True)
        try:
            response = gui_open_project(args.base_url, staged)
        finally:
            subprocess.run(["docker", "exec", args.container, "rm", "--", staged], check=True)
        if response.get("projectName") != name:
            raise RuntimeError(f"unexpected imported project: {response}")
    listing = {row["projectName"]: row for row in list_projects_with_status(args.base_url)}
    if listing[name].get("hasUnresolvedResources") is True:
        gui_confirm_existing_project_resources(args.base_url, name,
                                               expected_market_symbols={manifest["sq_symbol"]})
    listing = {row["projectName"]: row for row in list_projects_with_status(args.base_url)}
    if listing[name].get("hasUnresolvedResources") is not False:
        raise RuntimeError("imported project has unresolved resources")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    imported = args.output_dir / "sq_imported_project.cfx"
    subprocess.run(["docker", "cp",
                    f"{args.container}:/home/squser/SQ/user/projects/{name}/project.cfx",
                    str(imported)], check=True)
    if verify(imported, manifest) != shape:
        raise RuntimeError("SQ changed the frozen project contract")
    preflight = {"decision": "PASS_RANDOM_RUN_PREFLIGHT", "project_name": name,
                 "source_sha256": digest(args.project), "imported_sha256": digest(imported),
                 "manifest_sha256": digest(args.manifest), "shape": shape,
                 "paper_authorized": False, "live_authorized": False}
    write_atomic(args.output_dir / "run_preflight.json", preflight)
    response = gui_start_project(args.base_url, name)
    write_atomic(args.output_dir / "start_receipt.json",
                 {"decision": "PASS_SQCLI_START", "project_name": name,
                  "response": response})
    final = run_monitor(
        base_url=args.base_url, project=name, limits=load_limits(args.manifest),
        status_file=args.output_dir / "watchdog_status.json",
        journal_file=args.output_dir / "watchdog_journal.jsonl",
        disk_path=Path("/mnt/volume-SQ"),
        artifacts=Path("/mnt/volume-SQ/user/projects") / name / "databanks",
        interval=5, allow_control=True, snapshot_fn=gui_snapshot,
        call_fn=gui_project_action_from_cli,
        final_stats_fn=partial(docker_project_final_stats, args.container),
        started_project=True)
    result = {"decision": "PASS_SUPERVISED_RANDOM_RUN",
              "project_name": name, "final": final,
              "paper_authorized": False, "live_authorized": False}
    write_atomic(args.output_dir / "supervised_run_receipt.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
