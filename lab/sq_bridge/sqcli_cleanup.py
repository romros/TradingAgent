#!/usr/bin/env python3
"""Audita i neteja temporals SQCLI amb guard obligatori de processos actius."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path


def allocated_bytes(path: Path) -> int:
    return sum(item.stat().st_blocks * 512 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def candidates(root: Path, now: datetime, log_days: int, test_days: int) -> dict[str, list[Path]]:
    older_logs = now - timedelta(days=log_days)
    older_tests = now - timedelta(days=test_days)
    stock = root / "internal/tmp/stock"
    logs = root / "logs"
    tests = root / "internal/testfiles"
    return {
        "stock_jars": sorted(stock.rglob("*.jar")) if stock.exists() else [],
        "old_logs": sorted(item for item in logs.rglob("*.log")
                           if datetime.fromtimestamp(item.stat().st_mtime, timezone.utc) < older_logs) if logs.exists() else [],
        "old_testfiles": sorted(item for item in tests.rglob("*") if item.is_file()
                                and datetime.fromtimestamp(item.stat().st_mtime, timezone.utc) < older_tests) if tests.exists() else [],
    }


def active_sqcli() -> list[dict[str, str]]:
    output = subprocess.run(["docker", "ps", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Command}}"],
                            check=True, capture_output=True, text=True).stdout
    rows = []
    for line in output.splitlines():
        container_id, name, image, command = line.split("|", 3)
        if "sqcli" in name.lower() or "sqcli" in image.lower() or "sqcli" in command.lower():
            rows.append({"id": container_id, "name": name, "image": image, "command": command})
    return rows


def stopped_one_offs() -> list[dict[str, str]]:
    output = subprocess.run(["docker", "ps", "-a", "--filter", "status=exited", "--format",
                             "{{.ID}}|{{.Names}}|{{.Image}}"], check=True, capture_output=True, text=True).stdout
    rows = []
    for line in output.splitlines():
        container_id, name, image = line.split("|", 2)
        if name.startswith("sqcli-sqcli-run-"):
            rows.append({"id": container_id, "name": name, "image": image})
    return rows


def audit(root: Path, now: datetime, log_days: int, test_days: int) -> dict:
    groups = candidates(root, now, log_days, test_days)
    return {
        "schema_version": 1,
        "mode": "audit",
        "root": str(root),
        "active_sqcli": active_sqcli(),
        "stopped_one_offs": stopped_one_offs(),
        "root_allocated_bytes": allocated_bytes(root),
        "groups": {name: {"count": len(paths),
                           "allocated_bytes": sum(path.stat().st_blocks * 512 for path in paths),
                           "paths": [str(path) for path in paths]}
                   for name, paths in groups.items()},
        "policy": {"logs_min_age_days": log_days, "testfiles_min_age_days": test_days,
                   "stock_scope": "only *.jar", "global_prune": False},
        "testfiles_warning": "internal/testfiles are deleted only after the conservative age threshold and with no SQCLI active",
    }


def clean(root: Path, now: datetime, log_days: int, test_days: int) -> dict:
    before = audit(root, now, log_days, test_days)
    if before["active_sqcli"]:
        raise RuntimeError("ACTIVE_SQCLI_GUARD: cleanup refused")
    deleted = []
    for group in ("stock_jars", "old_logs", "old_testfiles"):
        for raw in before["groups"][group]["paths"]:
            path = Path(raw)
            allocated = path.stat().st_blocks * 512
            path.unlink()
            deleted.append({"group": group, "path": raw, "allocated_bytes": allocated})
    for directory in sorted((root / "internal/testfiles").rglob("*"), reverse=True):
        if directory.is_dir():
            try: directory.rmdir()
            except OSError: pass
    removed_containers = []
    for row in before["stopped_one_offs"]:
        subprocess.run(["docker", "rm", row["id"]], check=True, capture_output=True, text=True)
        removed_containers.append(row)
    after_bytes = allocated_bytes(root)
    return {**before, "mode": "cleanup", "deleted": deleted,
            "removed_containers": removed_containers,
            "after_allocated_bytes": after_bytes,
            "recovered_allocated_bytes": before["root_allocated_bytes"] - after_bytes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/roman/dockers-SQ/6ACC10"))
    parser.add_argument("--log-days", type=int, default=14)
    parser.add_argument("--testfiles-days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.log_days < 7 or args.testfiles_days < 7:
        raise SystemExit("La politica conservadora exigeix almenys 7 dies")
    now = datetime.now(timezone.utc)
    try:
        result = clean(args.root, now, args.log_days, args.testfiles_days) if args.apply else audit(
            args.root, now, args.log_days, args.testfiles_days)
    except RuntimeError as exc:
        print(json.dumps({"mode": "cleanup", "refused": True, "reason": str(exc)}, indent=2))
        raise SystemExit(2)
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(payload)
    print(payload, end="")


if __name__ == "__main__": main()
