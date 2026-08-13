#!/usr/bin/env python3
"""Mostra què sap realment l'Acadèmia de SQ i quin buit toca resoldre."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

RANK = {"mapped": 0, "evidenced": 1, "operational": 2, "tested": 3}


def report(data: dict, minimum: str = "tested") -> dict:
    capabilities = sorted(data["capabilities"], key=lambda item: item["order"])
    threshold = RANK[minimum]
    gaps = [item for item in capabilities if RANK[item["status"]] < threshold]
    return {
        "target_build": data["target_build"],
        "capabilities": len(capabilities),
        "by_status": dict(Counter(item["status"] for item in capabilities)),
        "minimum": minimum,
        "coverage_ratio": round((len(capabilities) - len(gaps)) / len(capabilities), 3),
        "next_gap": gaps[0] if gaps else None,
        "gaps": [{"order": item["order"], "id": item["id"], "status": item["status"], "next": item["next"]} for item in gaps],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--minimum", choices=RANK, default="tested")
    args = parser.parse_args()
    print(json.dumps(report(json.loads(args.coverage.read_text(encoding="utf-8")), args.minimum), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
