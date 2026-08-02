#!/usr/bin/env python3
"""Avalua si un resultat pot aportar evidència; mai executa ni promociona claims."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def assess(data: dict) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    required = {
        "id", "claim_id", "protocol_frozen_at", "executed_at", "sq_version", "dataset_id",
        "attempt_budget", "attempts_observed", "holdout_peeks", "costs", "artifacts", "result",
    }
    failures.extend(f"missing:{key}" for key in sorted(required - data.keys()))
    if failures:
        return {"eligible": False, "max_evidence_status": "captured", "failures": failures, "warnings": warnings}
    try:
        frozen = datetime.fromisoformat(data["protocol_frozen_at"].replace("Z", "+00:00"))
        executed = datetime.fromisoformat(data["executed_at"].replace("Z", "+00:00"))
        if frozen >= executed:
            failures.append("protocol_not_frozen_before_execution")
    except (TypeError, ValueError):
        failures.append("invalid_timestamps")
    if data["attempts_observed"] > data["attempt_budget"]:
        failures.append("attempt_budget_exceeded")
    if data["holdout_peeks"] != 0:
        failures.append("holdout_not_blind")
    for cost in ("spread", "commission", "slippage"):
        if cost not in data["costs"]:
            failures.append(f"missing_cost:{cost}")
    for artifact in ("config_sha256", "result_sha256"):
        value = data["artifacts"].get(artifact, "")
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            failures.append(f"invalid_artifact:{artifact}")
    if not data.get("limitations"):
        warnings.append("limitations_not_declared")
    passed = data["result"].get("passed")
    if not isinstance(passed, bool):
        failures.append("result_passed_not_boolean")
    return {
        "eligible": not failures,
        "max_evidence_status": "tested" if not failures else "captured",
        "claim_outcome": "supports" if passed is True else "contradicts" if passed is False else "unknown",
        "failures": failures,
        "warnings": warnings,
        "note": "La promoció de la claim requereix revisió humana; aquest gate no modifica el catàleg.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = assess(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
