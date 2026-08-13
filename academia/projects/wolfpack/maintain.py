#!/usr/bin/env python3
"""Finite daily Wolfpack checkpoint generator; no network or trading."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def age_seconds(path: Path, now: float) -> float | None:
    return None if not path.exists() else max(0.0, now - path.stat().st_mtime)


def checkpoint(root: Path, diary: Path, follows: Path, heartbeat: Path,
               output_dir: Path) -> dict:
    now = datetime.now(timezone.utc)
    output_dir.mkdir(parents=True, exist_ok=True)
    dated = output_dir / f"brief-{now:%Y-%m-%d}.json"
    latest = output_dir / "latest.json"
    paper = output_dir / "paper-latest.json"
    subprocess.run(["python3", str(root / "paper_follow.py"), "--follows", str(follows),
                    "--output", str(paper)], check=True)
    command = ["python3", str(root / "wolfpack.py"), "brief", "--diary", str(diary),
               "--follows", str(follows), "--paper", str(paper), "--output", str(dated)]
    subprocess.run(command, check=True)
    brief = json.loads(dated.read_text())
    clock = time.time()
    diary_age = age_seconds(diary, clock)
    heartbeat_age = age_seconds(heartbeat, clock)
    health = {
        "checked_at": now.isoformat(),
        "diary_age_seconds": diary_age,
        "follower_heartbeat_age_seconds": heartbeat_age,
        "diary_healthy": diary_age is not None and diary_age <= 5_400,
        "follower_healthy": heartbeat_age is not None and heartbeat_age <= 1_800,
    }
    result = {"health": health, "brief": brief}
    latest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    dated.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diary", type=Path, required=True)
    parser.add_argument("--follows", type=Path, required=True)
    parser.add_argument("--heartbeat", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--interval-seconds", type=int, default=86_400)
    args = parser.parse_args()
    if not 1 <= args.days <= 60:
        raise SystemExit("--days must be 1..60")
    for index in range(args.days):
        checkpoint(here, args.diary, args.follows, args.heartbeat, args.output_dir)
        if index + 1 < args.days:
            time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
