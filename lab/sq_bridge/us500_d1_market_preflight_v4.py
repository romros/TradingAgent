#!/usr/bin/env python3
"""Compose performance-blind US500 D1 readiness evidence for Alquimia v4."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def read_input(base: Path, value: str, label: str, reasons: list[str]) -> tuple[dict, dict]:
    path = resolve(base, value)
    if not path.is_file():
        reasons.append(f"{label.upper()}_MISSING")
        return {}, {"path": str(path), "exists": False}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        reasons.append(f"{label.upper()}_INVALID_JSON")
        data = {}
    return data, {"path": str(path), "exists": True, "bytes": path.stat().st_size,
                  "sha256": sha256(path)}


def compose(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text())
    required = ("campaign_id", "ostium_pair_id", "coverage", "mapping", "costs")
    missing = [name for name in required if not config.get(name)]
    if missing:
        raise ValueError(f"preflight config missing: {', '.join(missing)}")
    if config.get("schema_version") != 1:
        raise ValueError("preflight config must use schema_version=1")
    reasons: list[str] = []
    inputs = {}
    loaded = {}
    labels = ["coverage", "mapping", "costs"]
    if config.get("vix"):
        labels.append("vix")
    for label in labels:
        loaded[label], inputs[label] = read_input(
            config_path.parent, config[label], label, reasons)

    coverage, mapping, costs = (loaded[name] for name in (
        "coverage", "mapping", "costs"))
    vix = loaded.get("vix")
    if coverage.get("decision") != "PASS_HISTORICAL_COVERAGE":
        reasons.append("HISTORICAL_COVERAGE_NOT_PASS")
    if coverage.get("performance_accessed") is not False:
        reasons.append("COVERAGE_ACCESSED_PERFORMANCE")
    if mapping.get("decision") != "PASS_D1_SOURCE_MAPPING":
        reasons.append("D1_MAPPING_NOT_PASS")
    if mapping.get("performance_accessed") is not False:
        reasons.append("MAPPING_ACCESSED_PERFORMANCE")
    timing = (vix.get("timing_policy") or {}) if vix else {}
    if vix:
        if vix.get("decision") != "PASS_VIX_DATA_TIMING":
            reasons.append("VIX_TIMING_NOT_PASS")
        if (vix.get("spx_performance_accessed") is not False
                or vix.get("strategy_rule_defined") is not False
                or timing.get("same_session_use_allowed") is not False):
            reasons.append("VIX_ANTI_LOOKAHEAD_NOT_PROVEN")
    if costs.get("decision") != "PASS_COSTS_FROZEN" or costs.get("costs_frozen") is not True:
        reasons.append("EXECUTION_COSTS_NOT_FROZEN")
    if not (costs.get("by_notional") or {}).get("200"):
        reasons.append("COSTS_200_USDC_MISSING")
    if costs and (costs.get("paper_authorized") is not False
                  or costs.get("live_authorized") is not False):
        reasons.append("COST_INPUT_AUTHORIZATION_INVALID")

    decision = "PASS" if not reasons else "BLOCK"
    result = {
        "schema_version": 1, "stage": "market_preflight",
        "campaign_id": config["campaign_id"], "decision": decision,
        "candidate_ids": [], "holdout_accessed": False, "evidence_class": "observed",
        "market_executable": decision == "PASS", "data_gate": "PASS" if decision == "PASS" else "BLOCK",
        "ostium_pair_id": config["ostium_pair_id"], "performance_accessed": False,
        "historical_coverage_pass": coverage.get("historical_coverage_pass") is True,
        "historical_expected_observations": coverage.get("historical_expected_observations"),
        "historical_complete_observations": coverage.get("historical_complete_observations"),
        "historical_overall_coverage_ratio": coverage.get("historical_overall_coverage_ratio"),
        "historical_minimum_period_coverage_ratio": coverage.get("historical_minimum_period_coverage_ratio"),
        "historical_period_coverage": coverage.get("historical_period_coverage"),
        "source_mapping_pass": mapping.get("decision") == "PASS_D1_SOURCE_MAPPING",
        "proxy_candle_coverage_pct": (
            mapping.get("common_complete_session_coverage_ratio", 0) * 100),
        "return_correlation": mapping.get("d1_close_return_correlation"),
        "execution_economics_complete": costs.get("costs_frozen") is True,
        "future_periods_sealed": True,
        "campaign_config_path": str(config_path),
        "campaign_config_sha256": sha256(config_path),
        "risk_state_timing_pass": (
            vix.get("decision") == "PASS_VIX_DATA_TIMING" if vix else None),
        "vix_earliest_use": timing.get("earliest_use") if vix else None,
        "cost_notional_usdc": 200,
        "input_receipts": inputs,
        "blocking_reasons": sorted(set(reasons)),
        "next_stage_authorized": "hypothesis_screen" if decision == "PASS" else None,
        "sqcli_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=(Path(os.environ["ALQUIMIA_STAGE_ARTIFACT"])
                                 if os.environ.get("ALQUIMIA_STAGE_ARTIFACT") else None))
    args = parser.parse_args()
    if args.output is None:
        raise SystemExit("--output or ALQUIMIA_STAGE_ARTIFACT is required")
    result = compose(args.config)
    write_atomic(args.output, result)
    print(json.dumps({"decision": result["decision"],
                      "blocking_reasons": result["blocking_reasons"]}, indent=2))


if __name__ == "__main__":
    main()
