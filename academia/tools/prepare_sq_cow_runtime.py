#!/usr/bin/env python3
"""Prepara una còpia SQ descartable; per defecte només calcula i valida."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def tree_bytes(root: Path, excluded: set[Path] | None = None) -> int:
    excluded = excluded or set()
    total = 0
    for path in root.rglob("*"):
        if any(path == item or item in path.parents for item in excluded):
            continue
        if path.is_file():
            total += path.stat().st_size
    return total


def existing_ancestor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def assess(internal: Path, user: Path, destination: Path, allowed_root: Path, active_sq_projects: int) -> dict:
    blockers: list[str] = []
    try:
        destination.resolve().relative_to(allowed_root.resolve())
    except ValueError:
        blockers.append("destination_outside_academia_runtime")
    if active_sq_projects:
        blockers.append(f"sq_busy:{active_sq_projects}")
    for label, path in (("internal", internal), ("user", user), ("history", user / "data/History")):
        if not path.exists():
            blockers.append(f"missing_source:{label}")

    excluded = {user / "data/History"}
    required = tree_bytes(internal) + tree_bytes(user, excluded)
    free = shutil.disk_usage(existing_ancestor(destination.parent)).free
    if free < int(required * 1.2):
        blockers.append("insufficient_space_20pct_margin")
    return {
        "ready_to_copy": not blockers,
        "blockers": blockers,
        "copy_bytes": required,
        "free_bytes": free,
        "history_mount": {"source": str(user / "data/History"), "read_only": True},
        "write_mounts": {
            "internal": str(destination / "internal"),
            "user": str(destination / "user"),
            "logs": str(destination / "logs"),
        },
    }


def prepare(internal: Path, user: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"runtime ja existeix: {destination}")
    destination.mkdir(parents=True)
    shutil.copytree(internal, destination / "internal")
    shutil.copytree(user, destination / "user", ignore=lambda directory, names: {"History"} if Path(directory) == user / "data" else set())
    (destination / "user/data/History").mkdir(parents=True, exist_ok=True)
    (destination / "logs").mkdir()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--internal", type=Path, required=True)
    parser.add_argument("--user", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=root / "runtime/build143-final-capability-tests")
    parser.add_argument("--active-sq-projects", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    allowed = root / "runtime"
    report = assess(args.internal, args.user, args.destination, allowed, args.active_sq_projects)
    report["mode"] = "execute" if args.execute else "dry_run"
    if args.execute and report["ready_to_copy"]:
        prepare(args.internal, args.user, args.destination)
        report["prepared"] = True
    else:
        report["prepared"] = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_to_copy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
