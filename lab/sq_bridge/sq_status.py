#!/usr/bin/env python3
"""Genera un estat compacte i determinista d'una campanya SQ."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ERROR_MARKERS = ("error", "exception", "failed", "outofmemory")
PHASE_MARKERS = (
    ("all tasks completed", "completed"),
    ("retest", "retesting"),
    ("project started", "building"),
    ("initializing backtest data", "loading_data"),
)


def build_status(project_dir: Path) -> dict:
    logs = sorted((project_dir / "log").glob("global_log_*.log"))
    latest_log = logs[-1] if logs else None
    text = latest_log.read_text(encoding="utf-8", errors="replace") if latest_log else ""
    lowered = text.lower()
    phase = "not_started"
    for marker, candidate_phase in PHASE_MARKERS:
        if marker in lowered:
            phase = candidate_phase
            break

    errors = [line.strip() for line in text.splitlines() if any(m in line.lower() for m in ERROR_MARKERS)]
    databanks: dict[str, int] = {}
    root = project_dir / "databanks"
    if root.exists():
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            databanks[folder.name] = sum(1 for _ in folder.glob("*.sqx"))

    return {
        "schema_version": 1,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.name,
        "phase": phase,
        "databanks": databanks,
        "strategies_total_on_disk": sum(databanks.values()),
        "errors": errors[-10:],
        "latest_log": str(latest_log) if latest_log else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    status = build_status(args.project_dir)
    rendered = json.dumps(status, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
