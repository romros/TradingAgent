#!/usr/bin/env python3
"""Compile one replay-verified crypto H4 stable region into an SQ plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_signal_semantics_v4 import verify as verify_semantics
from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _bounds(members: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if len(members) < 3:
        raise ValueError("SQ plan requires a central point and two stable neighbors")
    names = set(next(iter(members.values())))
    if any(set(parameters) != names for parameters in members.values()):
        raise ValueError("stable region parameter schemas differ")
    result = {}
    for name in sorted(names):
        values = sorted({parameters[name] for parameters in members.values()})
        result[name] = {"minimum": values[0], "maximum": values[-1],
                        "allowed_values": values}
    return result


def compile_plan(*, selector_path: Path, candidate_id: str, design_path: Path,
                 semantics_path: Path, sq_resource_path: Path,
                 output_path: Path) -> dict[str, Any]:
    paths = [path.resolve() for path in (selector_path, design_path, semantics_path,
                                         sq_resource_path)]
    if any(not path.is_file() for path in paths):
        raise ValueError("SQ generation plan input missing")
    selector_path, design_path, semantics_path, resource_path = paths
    selector, design, resource = (_load(path) for path in
                                  (selector_path, design_path, resource_path))
    semantics = verify_semantics(semantics_path)
    if (selector.get("decision") != "PASS_STABLE_REGIONS"
            or selector.get("replay_verified") is not True
            or not isinstance(selector.get("replay_receipt"), dict)
            or selector.get("validation_accessed") is not False
            or selector.get("oos_accessed") is not False
            or selector.get("holdout_accessed") is not False):
        raise ValueError("stable-region selector is not replay verified")
    matches = [row for row in selector.get("selected_regions", [])
               if row.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise ValueError("candidate is not uniquely selected")
    region = matches[0]
    if (not semantics["valid"]
            or semantics["contract"]["experiment_design_sha256"] != _sha(design_path)
            or resource.get("decision") != "PASS_SQ_H4_PROXY_RESOURCE"
            or resource.get("campaign_id") != region.get("campaign_id")
            or resource.get("timeframe") != "H4"
            or resource.get("research_authorized") is not False):
        raise ValueError("SQ resource/design/semantics chain invalid")
    branch_matches = [row for row in design.get("branches", [])
                      if row.get("hypothesis_id") == region.get("hypothesis_id")]
    if len(branch_matches) != 1:
        raise ValueError("selected hypothesis absent from sealed design")
    branch = branch_matches[0]
    sq = semantics["contract"]["strategyquant_generation_contract"]
    money = sq["money_management"]
    result = {
        "schema_version": 1, "stage": "sq_generation_plan",
        "decision": "PASS_SQ_PLAN_READY", "candidate_id": candidate_id,
        "campaign_id": region["campaign_id"], "hypothesis_id": region["hypothesis_id"],
        "market": region["market"], "symbol": resource["symbol"],
        "instrument": resource["instrument"]["name"], "timeframe": "H4",
        "timezone": "Etc/UTC", "mechanism": region["mechanism"],
        "direction": region["direction"], "search_profile": region["profile"],
        "central_attempt": region["central_attempt"],
        "central_parameters": region["central_parameters"],
        "stable_member_attempts": region["member_attempts"],
        "parameter_search_space": _bounds(region["member_parameters"]),
        "generation_type": "genetic-evolution",
        "attempt_budget": sq["nominal_evaluations"],
        "sq_genetic_shape": {"islands": sq["islands"],
                             "population_per_island": sq["population_per_island"],
                             "max_generations": sq["max_generations"],
                             "nominal_evaluations": sq["nominal_evaluations"]},
        "genetic_parameters": {key: sq[key] for key in (
            "crossover_probability_pct", "mutation_probability_pct",
            "migration_every_generations", "migration_rate_pct",
            "initial_population_mode")},
        "maximum_rules": sq["maximum_rules"],
        "initial_capital_usdc": sq["initial_capital_usdc"],
        "normalized_notional_usdc": sq["normalized_notional_usdc"],
        "discovery_leverage": sq["discovery_leverage"],
        "money_management": {"method": money["method"],
                             "use_account_balance": money["use_account_balance"],
                             "maximum_size": money["maximum_size"],
                             "decimals": money["decimals_by_market"][region["market"]],
                             "fallback_to_size_one_allowed": False},
        "sq_embedded_spread": 0, "sq_embedded_commission": 0,
        "external_ostium_cost_revalidation_required": True,
        "maximum_promoted_candidates": 1,
        "inputs": {"selector": {"path": str(selector_path), "sha256": _sha(selector_path)},
                   "design": {"path": str(design_path), "sha256": _sha(design_path)},
                   "semantics": {"path": str(semantics_path), "sha256": _sha(semantics_path)},
                   "sq_resource": {"path": str(resource_path), "sha256": _sha(resource_path)}},
        "performance_scope": "train_only", "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "sqcli_authorized": False, "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(output_path.resolve(), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector", required=True, type=Path)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--design", required=True, type=Path)
    parser.add_argument("--semantics", required=True, type=Path)
    parser.add_argument("--sq-resource", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = compile_plan(selector_path=args.selector, candidate_id=args.candidate_id,
                          design_path=args.design, semantics_path=args.semantics,
                          sq_resource_path=args.sq_resource, output_path=args.output)
    print(json.dumps({key: result[key] for key in (
        "decision", "candidate_id", "symbol", "attempt_budget",
        "sq_genetic_shape", "sqcli_authorized")}, indent=2))


if __name__ == "__main__":
    main()
