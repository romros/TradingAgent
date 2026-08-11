#!/usr/bin/env python3
"""Run a bounded SQ runtime smoke for an imported custom-signal CFX."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Callable

from lab.sq_bridge.crypto_h4_cfx_v4 import verify_cfx
from lab.sq_bridge.sqcli_transport import (
    docker_project_final_stats,
    gui_project_action, gui_project_stats, gui_start_project,
    list_projects_with_status,
)


def _sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*, project: str, imported_cfx: Path, manifest_path: Path,
        target_iterations: int = 40, timeout_seconds: int = 300,
        base_url: str = "http://127.0.0.1:8080",
        list_fn: Callable[..., list[dict]] = list_projects_with_status,
        start_fn: Callable[..., dict] = gui_start_project,
        stats_fn: Callable[..., dict] = gui_project_stats,
        action_fn: Callable[..., str] = gui_project_action,
        final_stats_fn: Callable[..., dict] = docker_project_final_stats,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic) -> dict:
    if target_iterations < 1 or timeout_seconds < 1: raise ValueError("invalid smoke bound")
    imported_cfx, manifest_path = imported_cfx.resolve(), manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text())
    verified = verify_cfx(imported_cfx, manifest, require_archive_hash=False)
    custom = [key for key in verified["enabled_blocks"] if key.startswith("AlquimiaH4")]
    if len(custom) != 1 or manifest.get("project_name") != project:
        raise ValueError("custom signal smoke identity mismatch")
    listing = list_fn(base_url)
    matches = [row for row in listing if row.get("projectName") == project]
    active_statuses = {1, 2, 3}
    running = [row.get("projectName") for row in listing
               if row.get("runningStatus") in active_statuses]
    if running or len(matches) != 1 or matches[0].get("hasUnresolvedResources") is not False:
        raise RuntimeError("SQ project is not clean and idle")
    existing_completed = matches[0].get("runningStatus") == 4
    if matches[0].get("runningStatus") not in {0, 4}:
        raise RuntimeError("SQ target has a non-runnable terminal state")
    if existing_completed:
        final_stats = final_stats_fn("sqcli-docker", project)
        if final_stats.get("generated", 0) < 1 or final_stats.get("accepted", 0) < 1:
            raise RuntimeError("completed custom signal smoke has no generated strategy")
        return {"schema_version": 1, "decision": "PASS_SQ_CUSTOM_SIGNAL_RUNTIME_SMOKE",
                "project_name": project, "custom_signal_block": custom[0],
                "target_iterations": target_iterations, "observed_iterations": None,
                "generated": final_stats["generated"], "accepted": final_stats["accepted"],
                "final_log_path": final_stats["log_path"],
                "final_log_sha256": final_stats["log_sha256"],
                "recovered_completed_run": True,
                "imported_cfx_path": str(imported_cfx),
                "imported_cfx_sha256": _sha(imported_cfx),
                "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
                "final_running_status": 4, "performance_claim_authorized": False,
                "strategy_promotion_authorized": False}
    if matches[0].get("strategies") not in (0, None):
        raise RuntimeError("SQ target databank is not clean")
    response = start_fn(base_url, project)
    if not isinstance(response, dict) or response.get("success") is None:
        raise RuntimeError("SQ custom signal smoke did not start")
    started, deadline, snapshots = True, clock_fn() + timeout_seconds, []
    stop_response = None
    try:
        while clock_fn() < deadline:
            snapshot = stats_fn(base_url, project, timeout_seconds=20)
            tasks = snapshot.get("tasksIterations")
            iterations = (tasks[0].get("iterations") if isinstance(tasks, list)
                          and len(tasks) == 1 and isinstance(tasks[0], dict) else None)
            snapshots.append({"iterations": iterations,
                              "running_status": snapshot.get("runningStatus"),
                              "strategies": snapshot.get("strategies")})
            if isinstance(iterations, int) and iterations >= target_iterations: break
            if snapshot.get("runningStatus") in {0, 4, 50}:
                break
            sleep_fn(2)
        else:
            raise TimeoutError("custom signal smoke timed out")
    finally:
        if started:
            latest = list_fn(base_url)
            row = next((item for item in latest if item.get("projectName") == project), None)
            if row is not None and row.get("runningStatus") in active_statuses:
                stop_response = action_fn(base_url, "stop", project)
    final = list_fn(base_url)
    row = next((item for item in final if item.get("projectName") == project), None)
    observed = max((item["iterations"] for item in snapshots
                    if isinstance(item["iterations"], int)), default=0)
    final_stats = final_stats_fn("sqcli-docker", project)
    if (row is None or row.get("runningStatus") not in {0, 4}
            or final_stats.get("generated", 0) < 1):
        raise RuntimeError("custom signal smoke has no clean runtime evidence")
    return {"schema_version": 1, "decision": "PASS_SQ_CUSTOM_SIGNAL_RUNTIME_SMOKE",
            "project_name": project, "custom_signal_block": custom[0],
            "target_iterations": target_iterations, "observed_iterations": observed,
            "generated": final_stats["generated"], "accepted": final_stats["accepted"],
            "final_log_path": final_stats["log_path"],
            "final_log_sha256": final_stats["log_sha256"],
            "snapshots": snapshots, "stop_response": stop_response,
            "imported_cfx_path": str(imported_cfx),
            "imported_cfx_sha256": _sha(imported_cfx),
            "manifest_path": str(manifest_path), "manifest_sha256": _sha(manifest_path),
            "final_running_status": row.get("runningStatus"),
            "recovered_completed_run": False, "performance_claim_authorized": False,
            "strategy_promotion_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--imported-cfx", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-iterations", type=int, default=40)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = run(project=args.project, imported_cfx=args.imported_cfx,
                 manifest_path=args.manifest, target_iterations=args.target_iterations,
                 timeout_seconds=args.timeout_seconds)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__": main()
