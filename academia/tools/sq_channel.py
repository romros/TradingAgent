#!/usr/bin/env python3
"""Selecciona el canal més segur per una operació SQ declarada."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def choose(operation: dict) -> dict:
    if operation.get("live_trading"):
        return {"decision": "REJECT", "reason": "L'Acadèmia no opera trading live."}
    if operation.get("artifact_available"):
        return {"decision": "artifact", "reason": "L'objectiu es resol sense mutar SQ."}
    if operation.get("sqcli_supported"):
        return {"decision": "sqcli", "reason": "Canal determinista disponible."}
    if not operation.get("gap_evidence"):
        return {"decision": "BLOCKED", "reason": "Cal demostrar el gap de SQCLI abans d'usar navegador."}
    if operation.get("ui_state_observable") and operation.get("agentic_one_off"):
        return {"decision": "pinchtab", "reason": "Pilot agentic efímer amb snapshot i postcondició."}
    if operation.get("ui_state_observable") and operation.get("repeatable_test"):
        return {"decision": "playwright", "reason": "Flux conegut que necessita assertions i trace."}
    return {"decision": "manual", "reason": "L'estat o la mutació no són prou verificables."}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", type=Path)
    args = parser.parse_args()
    print(json.dumps(choose(json.loads(args.operation.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
