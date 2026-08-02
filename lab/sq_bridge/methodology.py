#!/usr/bin/env python3
"""Valida el contracte quantitatiu versionat d'Alquimia."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_STAGES = ["market_preflight", "discovery", "temporal_validation", "robustness", "small_account_economics", "python_translation", "parity", "paper"]


def validate(config: dict) -> list[str]:
    errors: list[str] = []
    if config.get("stages") != EXPECTED_STAGES:
        errors.append("stages: ordre canonic incorrecte")
    split = config.get("temporal_split", {})
    values = [split.get(key) for key in ("train_pct", "validation_pct", "oos_pct", "final_holdout_pct")]
    if any(not isinstance(value, (int, float)) or value <= 0 for value in values):
        errors.append("temporal_split: percentatges positius obligatoris")
    elif sum(values) != 100:
        errors.append("temporal_split: els percentatges han de sumar 100")
    if split.get("embargo_bars", 0) < 1:
        errors.append("temporal_split: embargo_bars ha de ser positiu")
    principles = config.get("principles", {})
    if principles.get("sq_role") != "candidate_generator_only":
        errors.append("principles: SQ nomes pot generar candidats")
    if principles.get("holdout_policy") != "sealed_until_final_gate":
        errors.append("principles: el holdout final ha d'estar segellat")
    if config.get("discovery", {}).get("robustness_during_generation") is not False:
        errors.append("discovery: robustesa separada de la generacio")
    small = config.get("small_account", {})
    if small.get("canonical_capital_usdc") != config.get("capital_usdc"):
        errors.append("small_account: capital canonic inconsistent")
    grid = small.get("leverage_grid", [])
    if not grid or grid != sorted(set(grid)) or min(grid) < 1:
        errors.append("small_account: leverage_grid invalid")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    errors = validate(config)
    print(json.dumps({"valid": not errors, "methodology_id": config.get("methodology_id"), "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
