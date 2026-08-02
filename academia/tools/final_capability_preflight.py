#!/usr/bin/env python3
"""Gate de seguretat per a les últimes proves SQ; no executa ni modifica SQ."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CAPABILITIES = {"builder-improver", "monte-carlo-parameters", "export-crossplatform"}


def assess(plan: dict, active_sq_projects: int, runtime_ready: bool) -> dict:
    blockers: list[str] = []
    if plan.get("target_build") != "143.2708":
        blockers.append("wrong_target_build")
    write_root = str(plan.get("write_root", ""))
    if not write_root.startswith("academia/runtime/"):
        blockers.append("write_root_outside_academia")
    if plan.get("holdout_access") is not False:
        blockers.append("holdout_not_locked")
    if plan.get("live_trading_access") is not False:
        blockers.append("live_trading_not_forbidden")
    if plan.get("source_mounts_read_only") is not True:
        blockers.append("source_mounts_not_read_only")
    if active_sq_projects:
        blockers.append(f"sq_busy:{active_sq_projects}")
    if not runtime_ready:
        blockers.append("cow_runtime_not_proven")

    tests = plan.get("tests", [])
    ids = {test.get("capability") for test in tests}
    for missing in sorted(REQUIRED_CAPABILITIES - ids):
        blockers.append(f"missing_test:{missing}")
    for test in tests:
        capability = test.get("capability", "unknown")
        if test.get("uses_holdout") is not False:
            blockers.append(f"holdout_enabled:{capability}")
        if not test.get("required_artifacts"):
            blockers.append(f"artifacts_missing:{capability}")
        if not test.get("pass_condition"):
            blockers.append(f"pass_condition_missing:{capability}")

    return {
        "ready": not blockers,
        "decision": "RUN_FINAL_CAPABILITY_TESTS" if not blockers else "DO_NOT_START",
        "blockers": blockers,
        "note": "Aquest gate no autoritza holdout, trading ni escriptures fora d'academia/runtime.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--active-sq-projects", type=int, required=True)
    parser.add_argument("--runtime-ready", action="store_true")
    args = parser.parse_args()
    result = assess(json.loads(args.plan.read_text(encoding="utf-8")), args.active_sq_projects, args.runtime_ready)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
