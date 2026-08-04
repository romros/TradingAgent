#!/usr/bin/env python3
"""Construeix un manifest de realitat des d'SQX més evidència suplementària explícita."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_sqx_evidence import extract
from reality_transfer import REQUIRED, assess


LOCKED = {"candidate_id", "instrument", "generation_period"}


def build(extracted: dict, supplement: dict | None = None) -> dict:
    generation = extracted.get("generation_result", {})
    execution = extracted.get("execution_assumptions", {})
    known = {
        "candidate_id": extracted.get("candidate_id"),
        "instrument": execution.get("instrument"),
        "generation_period": {"start": generation.get("history_from"), "end": generation.get("history_to")},
    }
    supplement = supplement or {}
    conflicts = [key for key in LOCKED if key in supplement and supplement[key] != known[key]]
    if conflicts:
        return {
            "decision": "INCOMPLET",
            "manifest": None,
            "conflicts": sorted(conflicts),
            "missing": [],
            "reason": "El suplement contradiu camps extrets de l'SQX.",
        }
    manifest = {**known, **supplement}
    missing = sorted(REQUIRED - manifest.keys())
    invalid_known = sorted(key for key, value in known.items() if value is None or value == {"start": None, "end": None})
    missing = sorted(set(missing + invalid_known))
    if missing:
        return {
            "decision": "INCOMPLET",
            "manifest": None,
            "draft": manifest,
            "conflicts": [],
            "missing": missing,
            "reason": "L'SQX no conté règims, venue actual, mecanisme, holdout ni economia suficients per si sol.",
            "sqx_classification": extracted.get("classification"),
            "artifact_sha256": extracted.get("artifact_sha256"),
        }
    return {
        "decision": assess(manifest)["decision"],
        "manifest": manifest,
        "assessment": assess(manifest),
        "conflicts": [],
        "missing": [],
        "artifact_sha256": extracted.get("artifact_sha256"),
        "limits": "Els camps suplementaris necessiten evidència pròpia; l'SQX només prova els camps bloquejats.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sqx", type=Path)
    parser.add_argument("--stage", choices=("discovery", "validation", "oos", "holdout"))
    parser.add_argument("--supplement", type=Path)
    args = parser.parse_args()
    supplement = json.loads(args.supplement.read_text(encoding="utf-8")) if args.supplement else None
    print(json.dumps(build(extract(args.sqx, args.stage), supplement), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
