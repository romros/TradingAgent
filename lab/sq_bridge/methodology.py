#!/usr/bin/env python3
"""Valida el contracte quantitatiu versionat d'Alquimia."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_STAGES_V3 = ["market_preflight", "discovery", "temporal_validation", "robustness", "small_account_economics", "python_translation", "parity", "paper"]
EXPECTED_STAGES_V4 = ["market_preflight", "hypothesis_screen", "sq_generation", "temporal_validation", "robustness", "small_account_economics", "python_translation", "parity", "paper"]


def validate(config: dict) -> list[str]:
    errors: list[str] = []
    expected = EXPECTED_STAGES_V4 if config.get("schema_version", 1) >= 4 else EXPECTED_STAGES_V3
    if config.get("stages") != expected:
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
    generation = (config.get("sq_generation", {}) if config.get("schema_version", 1) >= 4
                  else config.get("discovery", {}))
    if generation.get("robustness_during_generation") is not False:
        errors.append("discovery: robustesa separada de la generacio")
    if config.get("schema_version", 1) >= 4:
        preflight = config.get("market_preflight", {})
        if preflight.get("performance_accessed") is not False:
            errors.append("market_preflight: rendiment ha d'estar segellat")
        if preflight.get("minimum_overall_observation_coverage_ratio", 0) < 0.9:
            errors.append("market_preflight: cobertura global massa feble")
        if preflight.get("minimum_each_period_coverage_ratio", 0) < 0.8:
            errors.append("market_preflight: cobertura per periode massa feble")
        screen = config.get("hypothesis_screen", {})
        if screen.get("future_periods_accessed") is not False:
            errors.append("hypothesis_screen: futurs han d'estar segellats")
        if screen.get("minimum_stable_neighbors", 0) < 1:
            errors.append("hypothesis_screen: regio estable obligatoria")
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
