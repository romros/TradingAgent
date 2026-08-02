#!/usr/bin/env python3
"""Normalitza gates d'Alquímia en una fitxa educativa; només llegeix artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(campaign_id: str, family: str, temporal: dict, costs: dict,
              temporal_path: Path, costs_path: Path) -> dict:
    decisions = temporal.get("decisions", [])
    survivors = [item for item in decisions if item.get("passed")]
    base = next((item for item in costs.get("scenarios", []) if item.get("name") == "base"), None)
    if base is None:
        raise ValueError("el cost gate no conté l'escenari base")
    cost_pass = bool(base.get("passed"))
    temporal_pass = bool(survivors)
    if temporal_pass and not cost_pass:
        insight = "TEMPORAL_PASS_COST_FAIL"
        decision = "REJECT"
        next_test = "Canviar la font d'edge o reduir fricció estructural; no afinar paràmetres."
    elif temporal_pass and cost_pass:
        insight = "TEMPORAL_AND_COST_PASS"
        decision = "CONTINUE"
        next_test = "Aplicar el següent gate preregistrat mantenint el holdout intacte."
    else:
        insight = "TEMPORAL_FAIL"
        decision = "REJECT"
        next_test = "Revisar la hipòtesi; no executar proves més cares."
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "family": family,
        "source_artifacts": [
            {"path": str(temporal_path), "sha256": sha256(temporal_path), "role": "temporal_gate"},
            {"path": str(costs_path), "sha256": sha256(costs_path), "role": "cost_gate"},
        ],
        "observations": {
            "temporal": {
                "input_count": temporal.get("input_count"),
                "survivor_count": temporal.get("survivor_count"),
                "survivors": [
                    {"strategy": item.get("strategy"), "metrics": item.get("metrics"), "checks": item.get("checks")}
                    for item in survivors
                ],
            },
            "cost_base": {
                "orders": costs.get("orders"), "assumptions": base.get("assumptions"),
                "metrics": base.get("metrics"), "monte_carlo": base.get("monte_carlo"),
                "passed": cost_pass,
            },
        },
        "assessment": {
            "decision": decision, "insight_code": insight,
            "reason": (
                "El candidat supera el gate temporal però perd l'edge després dels costos base."
                if insight == "TEMPORAL_PASS_COST_FAIL" else
                "El candidat supera els gates temporal i de costos."
                if insight == "TEMPORAL_AND_COST_PASS" else
                "Cap candidat supera el gate temporal."
            ),
            "next_test": next_test,
            "evidence_status": "tested",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--family", required=True)
    parser.add_argument("--temporal", required=True, type=Path)
    parser.add_argument("--costs", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = normalize(
        args.campaign_id, args.family,
        json.loads(args.temporal.read_text(encoding="utf-8")),
        json.loads(args.costs.read_text(encoding="utf-8")),
        args.temporal, args.costs,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
