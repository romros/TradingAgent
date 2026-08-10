#!/usr/bin/env python3
"""Recompute a trustworthy, performance-blind EURUSD v4 readiness status."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.eurusd_d1_market_preflight_v4 import compose, resolve
from lab.sq_bridge.ostium_small_account_cost_gate_v4 import derive


def _load(path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return raw, value


def build(summary_path: Path, costs_path: Path, config_path: Path) -> dict[str, Any]:
    summary_path, costs_path, config_path = (
        path.resolve() for path in (summary_path, costs_path, config_path))
    errors: list[str] = []
    try:
        summary_raw, summary = _load(summary_path)
        _, stored_costs = _load(costs_path)
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"schema_version": 1, "status": "INVALID_EVIDENCE",
                "errors": [str(exc)], "sqcli_authorized": False,
                "paper_authorized": False, "live_authorized": False}

    configured_costs = resolve(config_path.parent, str(config.get("costs", "")))
    if configured_costs != costs_path:
        errors.append("CONFIG_COST_PATH_MISMATCH")
    try:
        expected_costs = derive(summary, expected_pair_id="2",
                                expected_pair=("EUR", "USD"))
        expected_costs["source_sha256"] = hashlib.sha256(summary_raw).hexdigest()
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"COST_RECOMPUTATION_FAILED:{exc}")
        expected_costs = {}
    if stored_costs != expected_costs:
        errors.append("COST_ARTIFACT_STALE_OR_TAMPERED")
    try:
        preflight = compose(config_path)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"PREFLIGHT_RECOMPUTATION_FAILED:{exc}")
        preflight = {}

    if errors:
        status = "INVALID_EVIDENCE"
    elif preflight.get("decision") == "PASS":
        status = "READY_HYPOTHESIS_SCREEN"
    else:
        status = "COLLECTING_COSTS"
    return {
        "schema_version": 1,
        "campaign_id": config.get("campaign_id"),
        "status": status,
        "errors": errors,
        "cost_decision": expected_costs.get("decision"),
        "coverage": expected_costs.get("coverage"),
        "notional_observations": expected_costs.get("notional_observations"),
        "remaining_complete_captures_lower_bound": expected_costs.get(
            "remaining_complete_captures_lower_bound", 0),
        "preflight_decision": preflight.get("decision"),
        "blocking_reasons": preflight.get("blocking_reasons", []),
        "next_stage_authorized": preflight.get("next_stage_authorized"),
        # The preflight can authorize only the deterministic hypothesis screen.
        "sqcli_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    root = Path(__file__).parents[2]
    state = root / "data" / "ostium_economics_universe"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path,
                        default=state / "eurusd_ostium_execution_summary_latest.json")
    parser.add_argument("--costs", type=Path,
                        default=state / "eurusd_costs_latest_v4.json")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).with_name(
                            "eurusd_d1_market_preflight_v4_config.json"))
    args = parser.parse_args()
    result = build(args.summary, args.costs, args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(2 if result["status"] == "INVALID_EVIDENCE" else 0)


if __name__ == "__main__":
    main()
