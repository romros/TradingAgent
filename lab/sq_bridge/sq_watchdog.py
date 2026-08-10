#!/usr/bin/env python3
"""Deterministic, fail-safe monitor for one disposable SQ Builder project."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from functools import partial
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lab.sq_bridge.sqcli_transport import (
    docker_exec_http_call, docker_project_final_stats,
    gui_project_action_from_cli, gui_project_stats,
)


def sq_call(base_url: str, command: str) -> str:
    encoded = urllib.parse.quote(command, safe="=-_")
    with urllib.request.urlopen(f"{base_url}/call?cmd={encoded}", timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def metric(text: str, label: str, cast=float):
    match = re.search(rf"^{re.escape(label)}\s+([0-9.]+)", text, re.MULTILINE)
    return cast(match.group(1)) if match else None


def memory_available_bytes() -> int:
    text = Path("/proc/meminfo").read_text(encoding="utf-8")
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", text, re.MULTILINE)
    return int(match.group(1)) * 1024 if match else 0


def inventory_sqx(root: Path | None) -> list[dict]:
    if root is None or not root.exists():
        return []
    result = []
    for path in sorted(root.rglob("*.sqx")):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        stat = path.stat()
        result.append({
            "path": str(path.relative_to(root)),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": digest.hexdigest(),
        })
    return result


@dataclass(frozen=True)
class Limits:
    attempt_budget: int
    accepted_target: int | None = None
    wall_time_minutes: int | None = None
    stagnation_attempts: int | None = None
    min_free_memory_mib: int = 1024
    min_free_disk_mib: int = 2048

    def __post_init__(self) -> None:
        for name in ("attempt_budget", "accepted_target", "wall_time_minutes", "stagnation_attempts"):
            value = getattr(self, name)
            if value is not None and value < 1:
                raise ValueError(f"{name} must be positive")


def load_limits(manifest: Path, *, per_project_attempt_budget: int | None = None) -> Limits:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    budget = per_project_attempt_budget or data.get("attempt_budget_per_project")
    if budget is None:
        projects = data.get("symbols", [])
        total = data.get("attempt_budget")
        if not isinstance(total, int) or not projects or total % len(projects):
            raise ValueError("manifest must define an unambiguous per-project attempt budget")
        budget = total // len(projects)
    return Limits(
        attempt_budget=budget,
        accepted_target=data.get("accepted_target"),
        wall_time_minutes=data.get("wall_time_budget_minutes"),
        stagnation_attempts=data.get("stagnation_attempts"),
        min_free_memory_mib=data.get("min_free_memory_mib", 1024),
        min_free_disk_mib=data.get("min_free_disk_mib", 2048),
    )


def snapshot(base_url: str, project: str, disk_path: Path, artifacts: Path | None = None,
             *, call_fn: Callable[[str, str], str] = sq_call) -> dict:
    raw = call_fn(base_url, f"-project action=status name={project}")
    disk = shutil.disk_usage(disk_path)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "generated": metric(raw, "Strategies generated", int),
        "accepted_pct": metric(raw, "Accepted"),
        "in_databank": metric(raw, "In databank", int),
        "failed": metric(raw, "Failed", int),
        "strategies_per_hour": metric(raw, "Strategies per hour"),
        "memory_available_bytes": memory_available_bytes(),
        "disk_free_bytes": disk.free,
        "artifacts": inventory_sqx(artifacts),
        "raw_status": raw,
    }


def gui_snapshot(base_url: str, project: str, disk_path: Path,
                 artifacts: Path | None = None) -> dict:
    row = gui_project_stats(base_url, project)
    tasks = row.get("tasksIterations")
    task = tasks[0] if isinstance(tasks, list) and len(tasks) == 1 else {}
    engine = row.get("_engine", {})
    live_jobs = engine.get("totalJobsDone")
    generated = (live_jobs if isinstance(live_jobs, int)
                 and not isinstance(live_jobs, bool) and live_jobs >= 0 else None)
    accepted = row["strategies"]
    disk = shutil.disk_usage(disk_path)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project, "generated": generated,
        "accepted_pct": (accepted / generated * 100 if generated else None),
        "in_databank": accepted,
        "failed": engine.get("strategiesFailed"),
        "strategies_per_hour": _finite_number(engine.get("strategiesPerHour")),
        "backtests_performed": engine.get("backtestsPerformed"),
        "job_exceptions": engine.get("jobExceptionsCount"),
        "running_status": row["runningStatus"],
        "task_name": task.get("taskName"),
        "task_iterations": task.get("iterations"),
        "attempt_counter_source": ("engine.totalJobsDone_live_lower_bound"
                                   if generated is not None else None),
        "memory_available_bytes": memory_available_bytes(),
        "disk_free_bytes": disk.free, "artifacts": inventory_sqx(artifacts),
        "raw_status": json.dumps(row, sort_keys=True),
        "status_source": ("sq_gui_subscribed_websocket"
                          if generated is not None else "sq_gui_rest_degraded"),
    }


def _finite_number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def evaluate(current: dict, history: list[dict], limits: Limits, elapsed_seconds: float) -> tuple[str, str | None]:
    generated = current.get("generated")
    accepted = current.get("in_databank") or 0
    if generated is not None and generated >= limits.attempt_budget:
        return "BUDGET_REACHED", "ATTEMPT_BUDGET"
    if limits.accepted_target is not None and accepted >= limits.accepted_target:
        return "BUDGET_REACHED", "ACCEPTED_TARGET"
    if limits.wall_time_minutes is not None and elapsed_seconds >= limits.wall_time_minutes * 60:
        return "BUDGET_REACHED", "WALL_TIME_BUDGET"
    if current["memory_available_bytes"] < limits.min_free_memory_mib * 1024 * 1024:
        return "BROKEN", "LOW_HOST_MEMORY"
    if current["disk_free_bytes"] < limits.min_free_disk_mib * 1024 * 1024:
        return "BROKEN", "LOW_DISK"
    prior_generated = [item.get("generated") for item in history if item.get("generated") is not None]
    if generated is None:
        return "INVESTIGATE", "ATTEMPT_COUNTER_UNAVAILABLE"
    if prior_generated and generated == prior_generated[-1]:
        return "COMPUTE_STALL", None
    if limits.stagnation_attempts and accepted == 0 and generated >= limits.stagnation_attempts:
        return "SCIENTIFIC_STALL", "NO_ACCEPTED_WITHIN_STAGNATION_BUDGET"
    return ("HEALTHY" if accepted else "SELECTIVE"), None


def append_jsonl(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def run_monitor(
    *, base_url: str, project: str, limits: Limits, status_file: Path,
    journal_file: Path, disk_path: Path, artifacts: Path | None, interval: int,
    allow_control: bool, once: bool = False,
    snapshot_fn: Callable[..., dict] = snapshot,
    call_fn: Callable[[str, str], str] = sq_call,
    final_stats_fn: Callable[[str], dict] | None = None,
) -> dict:
    started = time.monotonic()
    history: list[dict] = []
    while True:
        try:
            status = snapshot_fn(base_url, project, disk_path, artifacts)
        except Exception as exc:  # monitoring must never stop SQ by accident
            status = {
                "observed_at": datetime.now(timezone.utc).isoformat(), "project": project,
                "state": "BROKEN", "reason": "MONITOR_ERROR", "error": repr(exc),
                "control_authorized": allow_control,
            }
        else:
            state, reason = evaluate(status, history, limits, time.monotonic() - started)
            status.update({"state": state, "reason": reason, "control_authorized": allow_control})
            history.append(status.copy())
        append_jsonl(journal_file, status)
        write_atomic(status_file, status)
        print(json.dumps({key: status.get(key) for key in ("observed_at", "generated", "in_databank", "state", "reason")}), flush=True)

        terminal = status.get("reason") in {
            "ATTEMPT_BUDGET", "ACCEPTED_TARGET", "WALL_TIME_BUDGET",
            "LOW_HOST_MEMORY", "LOW_DISK", "NO_ACCEPTED_WITHIN_STAGNATION_BUDGET",
        }
        if terminal:
            if allow_control:
                status["pause_response"] = call_fn(base_url, f"-project action=pause name={project}")
                status["stop_response"] = call_fn(base_url, f"-project action=stop name={project}")
                append_jsonl(journal_file, {**status, "event": "CONTROL_APPLIED"})
                write_atomic(status_file, status)
            if final_stats_fn is not None:
                try:
                    final = final_stats_fn(project)
                except Exception as exc:
                    status["final_stats_error"] = repr(exc)
                else:
                    final_log_path = status_file.with_suffix(
                        status_file.suffix + ".sq-final.log")
                    write_text_atomic(final_log_path, final.pop("log_text"))
                    status.update({
                        "generated": final["generated"],
                        "in_databank": final["accepted"],
                        "rejected": final["rejected"],
                        "attempt_counter_source": final["attempt_counter_source"],
                        "sq_final_log_path": str(final_log_path.resolve()),
                        "sq_container_log_path": final["log_path"],
                        "sq_final_log_sha256": final["log_sha256"],
                    })
                    status["artifacts"] = inventory_sqx(artifacts)
                append_jsonl(journal_file, {**status, "event": "FINAL_STATS"})
                write_atomic(status_file, status)
            return status
        if once:
            return status
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=("gui-websocket", "http", "docker-exec"),
                        default="gui-websocket")
    parser.add_argument("--base-url", default="http://127.0.0.1:5050")
    parser.add_argument("--container", default="sqcli-docker")
    parser.add_argument("--api-port", type=int, default=5050)
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--attempt-budget", type=int, help="Explicit per-project override")
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--journal-file", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--disk-path", type=Path, default=Path("/mnt/volume-SQ"))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--allow-control", action="store_true", help="Permit pause+stop at a frozen terminal gate")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    limits = load_limits(args.manifest, per_project_attempt_budget=args.attempt_budget)
    if args.transport == "gui-websocket":
        caller = gui_project_action_from_cli
        snapshot_with_transport = gui_snapshot
        finalizer = partial(docker_project_final_stats, args.container)
    elif args.transport == "http":
        caller = sq_call
        snapshot_with_transport = partial(snapshot, call_fn=caller)
        finalizer = None
    else:
        caller = lambda _base_url, command: docker_exec_http_call(
            args.container, command, api_port=args.api_port)
        snapshot_with_transport = partial(snapshot, call_fn=caller)
        finalizer = partial(docker_project_final_stats, args.container)
    run_monitor(
        base_url=args.base_url, project=args.project, limits=limits,
        status_file=args.status_file, journal_file=args.journal_file,
        disk_path=args.disk_path, artifacts=args.artifacts, interval=args.interval,
        allow_control=args.allow_control, once=args.once,
        snapshot_fn=snapshot_with_transport, call_fn=caller,
        final_stats_fn=finalizer,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
