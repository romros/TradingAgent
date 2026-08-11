#!/usr/bin/env python3
"""Select stable, non-overlapping crypto H4 train regions deterministically."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from lab.sq_bridge.crypto_h4_experiment_design_v4 import parameter_axes


MAX_DISTANCE = .15
NEAREST = 4
MIN_NEIGHBORS_PASSING = 2
GLOBAL_BUDGET = 60


def _pf(value: Any) -> float:
    if value == "Infinity":
        return math.inf
    result = float(value)
    return result if math.isfinite(result) else -math.inf


def _rank(region: dict[str, Any]) -> tuple:
    stress = region["central_metrics"]["scenarios"]["stress"]
    return (-float(stress["expectancy_usdc_per_trade"]),
            -_pf(stress["profit_factor"]),
            float(stress["max_drawdown_usdc"]),
            region["hypothesis_id"], region["central_attempt"])


def _axis_indexes(branch: dict[str, Any], prereg: dict[str, Any]) -> dict[str, dict[Any, int]]:
    axes = parameter_axes(
        branch["profile"], prereg["profile_parameter_ranges"][branch["profile"]])
    return {name: {value: index for index, value in enumerate(values)}
            for name, values in axes.items()}


def normalized_distance(left: dict[str, Any], right: dict[str, Any],
                        indexes: dict[str, dict[Any, int]]) -> float:
    distance = 0.0
    for name, values in indexes.items():
        if left.get(name) not in values or right.get(name) not in values:
            raise ValueError(f"parameter outside sealed axis: {name}")
        maximum = max(values.values())
        distance += (abs(values[left[name]] - values[right[name]]) /
                     maximum if maximum else 0.0)
    return distance


def _valid_row(row: dict[str, Any]) -> None:
    if (not isinstance(row.get("attempt"), int) or row["attempt"] <= 0
            or not isinstance(row.get("parameters"), dict)
            or not isinstance(row.get("closed_trades"), int)
            or isinstance(row.get("closed_trades"), bool) or row["closed_trades"] < 0
            or row.get("decision") not in {"PASS_POINT", "REJECT_POINT"}
            or not isinstance(row.get("scenarios"), dict)):
        raise ValueError("invalid train screen row")
    for scenario in ("base", "conservative", "stress"):
        metrics = row["scenarios"].get(scenario) or {}
        for key in ("net_pnl_usdc", "expectancy_usdc_per_trade",
                    "profit_factor", "max_drawdown_usdc",
                    "positive_calendar_years_ratio"):
            if key not in metrics:
                raise ValueError("incomplete train screen metrics")
        for key in ("net_pnl_usdc", "expectancy_usdc_per_trade",
                    "max_drawdown_usdc", "positive_calendar_years_ratio"):
            value = metrics[key]
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value)):
                raise ValueError("non-finite train screen metrics")
        if (metrics["max_drawdown_usdc"] < 0
                or not 0 <= metrics["positive_calendar_years_ratio"] <= 1
                or (metrics["profit_factor"] != "Infinity"
                    and (not isinstance(metrics["profit_factor"], (int, float))
                         or isinstance(metrics["profit_factor"], bool)
                         or not math.isfinite(metrics["profit_factor"])
                         or metrics["profit_factor"] < 0))):
            raise ValueError("invalid train screen metric range")


def regions_for_branch(rows: list[dict[str, Any]], branch: dict[str, Any],
                       prereg: dict[str, Any]) -> list[dict[str, Any]]:
    if len({row.get("attempt") for row in rows}) != len(rows):
        raise ValueError("duplicate train screen attempt")
    for row in rows:
        _valid_row(row)
    indexes = _axis_indexes(branch, prereg)
    regions = []
    for central in rows:
        if central["decision"] != "PASS_POINT":
            continue
        distances = sorted(
            ((normalized_distance(central["parameters"], other["parameters"], indexes),
              other["attempt"], other) for other in rows
             if other["attempt"] != central["attempt"]),
            key=lambda item: (item[0], item[1]))[:NEAREST]
        local = [item for item in distances if item[0] <= MAX_DISTANCE]
        passing = [item for item in local if item[2]["decision"] == "PASS_POINT"]
        if len(passing) < MIN_NEIGHBORS_PASSING:
            continue
        members = [central["attempt"], *(item[2]["attempt"] for item in passing)]
        member_rows = {central["attempt"]: central,
                       **{item[2]["attempt"]: item[2] for item in passing}}
        member_distances = {str(central["attempt"]): 0.0,
                            **{str(item[2]["attempt"]): item[0] for item in passing}}
        identity = (f"{branch['hypothesis_id']}|{central['attempt']}|"
                    f"{','.join(str(value) for value in sorted(members))}")
        regions.append({
            "candidate_id": f"alq4_{hashlib.sha256(identity.encode()).hexdigest()[:16]}",
            "hypothesis_id": branch["hypothesis_id"],
            "campaign_id": branch["campaign_id"], "market": branch["market"],
            "mechanism": branch["mechanism"], "direction": branch["direction"],
            "profile": branch["profile"], "central_attempt": central["attempt"],
            "central_parameters": central["parameters"],
            "central_metrics": {"closed_trades": central["closed_trades"],
                                "scenarios": central["scenarios"]},
            "member_attempts": sorted(members),
            "member_parameters": {str(attempt): member_rows[attempt]["parameters"]
                                  for attempt in sorted(members)},
            "member_distances": member_distances,
            "nearest_points_considered": [item[2]["attempt"] for item in distances],
            "maximum_neighbor_distance": max(item[0] for item in passing),
            "selection_scope": "train_only", "validation_accessed": False,
            "oos_accessed": False, "holdout_accessed": False,
            "paper_authorized": False, "live_authorized": False,
        })
    return sorted(regions, key=_rank)


def select_global(regions: list[dict[str, Any]], budget: int = GLOBAL_BUDGET) -> dict[str, Any]:
    if budget != GLOBAL_BUDGET:
        raise ValueError("global candidate budget must remain sealed at 60")
    candidate_ids = [region.get("candidate_id") for region in regions]
    if (any(not isinstance(value, str) or not value for value in candidate_ids)
            or len(candidate_ids) != len(set(candidate_ids))):
        raise ValueError("stable region candidate IDs must be unique")
    selected: list[dict[str, Any]] = []
    claimed: dict[str, set[int]] = {}
    suppressed = []
    for region in sorted(regions, key=_rank):
        hypothesis = region["hypothesis_id"]
        members = set(region["member_attempts"])
        overlap = members & claimed.setdefault(hypothesis, set())
        if overlap:
            suppressed.append({"candidate_id": region["candidate_id"],
                               "reason": "OVERLAPPING_BETTER_RANKED_REGION",
                               "shared_attempts": sorted(overlap)})
            continue
        if len(selected) >= budget:
            suppressed.append({"candidate_id": region["candidate_id"],
                               "reason": "GLOBAL_ACCEPTED_CANDIDATE_BUDGET_60"})
            continue
        selected.append(region)
        claimed[hypothesis].update(members)
    return {
        "schema_version": 1,
        "decision": "PASS_STABLE_REGIONS" if selected else "REJECT_NO_STABLE_REGION",
        "selected_candidate_ids": [row["candidate_id"] for row in selected],
        "selected_regions": selected, "suppressed_regions": suppressed,
        "global_budget": GLOBAL_BUDGET, "regions_before_suppression": len(regions),
        "performance_scope": "train_only", "validation_accessed": False,
        "oos_accessed": False, "holdout_accessed": False,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False,
    }


def canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
