#!/usr/bin/env python3
"""Avalua decisions de transferència sobre casos versionats i falsables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reality_transfer import assess


def benchmark(suite: dict) -> dict:
    details = []
    for item in suite.get("cases", []):
        result = assess(item["input"])
        expected = item["expected_decision"]
        details.append({
            "id": item["id"],
            "expected": expected,
            "actual": result["decision"],
            "passed": result["decision"] == expected,
            "main_risk": result["main_risk"],
        })
    passed = sum(item["passed"] for item in details)
    total = len(details)
    return {
        "suite": suite.get("id", "unknown"),
        "passed": passed == total and total > 0,
        "score": passed / total if total else 0,
        "cases": total,
        "details": details,
        "limits": "Casos sintètics: validen la política de decisió, no rendibilitat.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite", type=Path)
    args = parser.parse_args()
    result = benchmark(json.loads(args.suite.read_text(encoding="utf-8")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
