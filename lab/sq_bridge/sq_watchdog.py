#!/usr/bin/env python3
"""Watchdog lleuger per a campanyes SQ actives via l'API interna."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


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


def snapshot(base_url: str, project: str, disk_path: Path) -> dict:
    raw = sq_call(base_url, f"-project action=status name={project}")
    disk = shutil.disk_usage(disk_path)
    generated = metric(raw, "Strategies generated", int)
    accepted_pct = metric(raw, "Accepted")
    in_databank = metric(raw, "In databank", int)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "generated": generated,
        "accepted_pct": accepted_pct,
        "in_databank": in_databank,
        "failed": metric(raw, "Failed", int),
        "strategies_per_hour": metric(raw, "Strategies per hour"),
        "memory_available_bytes": memory_available_bytes(),
        "disk_free_bytes": disk.free,
        "raw_status": raw,
    }


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--disk-path", type=Path, default=Path("/mnt/volume-SQ"))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--zero-acceptance-limit", type=int, default=1000)
    parser.add_argument("--min-free-memory-mib", type=int, default=1024)
    parser.add_argument("--min-free-disk-mib", type=int, default=2048)
    args = parser.parse_args()

    while True:
        status = snapshot(args.base_url, args.project, args.disk_path)
        reason = None
        if status["in_databank"] and status["in_databank"] >= 20:
            reason = "TARGET_REACHED"
        elif status["generated"] is not None and status["generated"] >= args.zero_acceptance_limit and not status["in_databank"]:
            reason = "ZERO_ACCEPTANCE"
        elif status["memory_available_bytes"] < args.min_free_memory_mib * 1024 * 1024:
            reason = "LOW_HOST_MEMORY"
        elif status["disk_free_bytes"] < args.min_free_disk_mib * 1024 * 1024:
            reason = "LOW_DISK"

        status["watchdog_reason"] = reason
        write_atomic(args.status_file, status)
        print(json.dumps({key: status[key] for key in ("observed_at", "generated", "in_databank", "failed", "watchdog_reason")}), flush=True)

        if reason:
            if reason != "TARGET_REACHED":
                status["stop_response"] = sq_call(args.base_url, f"-project action=stop name={args.project}")
                write_atomic(args.status_file, status)
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
