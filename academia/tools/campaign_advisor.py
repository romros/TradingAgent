#!/usr/bin/env python3
"""Explica un fracàs conegut en el format curt del skill d'Alquímia."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LABELS = {"REJECT": "DESCARTAR", "NO_CANDIDATE": "DESCARTAR", "CONTINUE": "CONTINUAR"}


def advise(memory: dict, family: str) -> dict:
    matches = [entry for entry in memory.get("entries", []) if entry["family"] == family]
    if not matches:
        return {
            "decision": "PROVA DIRIGIDA",
            "motiu": "No hi ha una campanya equivalent registrada; falta evidència pròpia.",
            "risc_principal": "extrapolar una altra família",
            "seguent_pas": "Pre-registrar una campanya barata amb holdout nou.",
            "evidencia": "falta",
        }
    if len(matches) > 1:
        raise ValueError(f"família amb memòries ambigües: {family}")
    entry = matches[0]
    return {
        "decision": LABELS.get(entry["decision"], "PROVA DIRIGIDA"),
        "motiu": entry["lesson"],
        "risc_principal": entry["failure_code"],
        "seguent_pas": entry["next_direction"],
        "evidencia": entry["evidence"],
        "no_repetir": entry["do_not_repeat"],
    }


def render(result: dict) -> str:
    lines = [
        f"DECISIÓ: {result['decision']}",
        f"MOTIU: {result['motiu']}",
        f"RISC PRINCIPAL: {result['risc_principal']}",
        f"SEGÜENT PAS: {result['seguent_pas']}",
        f"EVIDÈNCIA: {result['evidencia']}",
    ]
    if "no_repetir" in result:
        lines.append(f"NO REPETIR: {result['no_repetir']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("family")
    parser.add_argument(
        "--failure-memory", type=Path,
        default=Path(__file__).resolve().parents[1] / "experiments/failure-memory.json",
    )
    args = parser.parse_args()
    memory = json.loads(args.failure_memory.read_text(encoding="utf-8"))
    print(render(advise(memory, args.family)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
