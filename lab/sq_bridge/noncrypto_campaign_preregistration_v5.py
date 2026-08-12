#!/usr/bin/env python3
"""Verify the sealed, performance-blind Alquimia non-crypto v5 campaign."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.noncrypto_playbook_hypotheses_v5 import validate as validate_catalog


ROOT = Path(__file__).resolve().parents[2]
PREREG = Path(__file__).with_name("noncrypto_campaign_preregistration_v5.json")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_path(text: str) -> Path:
    path = (ROOT / text).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {text}") from exc
    if not path.is_file():
        raise ValueError(f"input missing: {text}")
    return path


def _verify_splits(splits: dict[str, Any]) -> None:
    expected_segments = ("train", "validation", "oos", "holdout")
    for market, periods in splits.items():
        previous_end: date | None = None
        for segment in expected_segments:
            if segment not in periods or len(periods[segment]) != 2:
                raise ValueError(f"{market}: missing temporal segment {segment}")
            start, end = map(date.fromisoformat, periods[segment])
            if start > end:
                raise ValueError(f"{market}: reversed {segment}")
            if previous_end is not None and start <= previous_end:
                raise ValueError(f"{market}: temporal overlap before {segment}")
            previous_end = end


def verify(path: Path = PREREG) -> dict[str, Any]:
    doc = _load(path)
    if doc.get("stage") != "PREREGISTERED_BEFORE_PERFORMANCE":
        raise ValueError("campaign is not preregistered")
    for field in ("performance_accessed", "holdout_accessed", "sqcli_executed", "legacy_candidates_reused", "crypto_allowed"):
        if doc.get(field) is not False:
            raise ValueError(f"{field} must be false")

    inputs = doc["inputs"]
    audit_path = _repo_path(inputs["market_audit_path"])
    catalog_path = _repo_path(inputs["hypothesis_catalog_path"])
    if _hash(audit_path) != inputs["market_audit_sha256"]:
        raise ValueError("market audit hash mismatch")
    if _hash(catalog_path) != inputs["hypothesis_catalog_sha256"]:
        raise ValueError("hypothesis catalog hash mismatch")
    audit = _load(audit_path)
    if audit.get("performance_accessed") or audit.get("holdout_accessed"):
        raise ValueError("market audit is performance-tainted")
    catalog_result = validate_catalog(catalog_path)

    _verify_splits(doc["temporal_splits"])
    spaces = doc["hypothesis_search_spaces"]
    ids = [item["hypothesis_id"] for item in spaces]
    catalog_ids = [item["hypothesis_id"] for item in _load(catalog_path)["hypotheses"]]
    if len(ids) != len(set(ids)) or set(ids) != set(catalog_ids):
        raise ValueError("search spaces must match unique catalog hypotheses")
    for item in spaces:
        if len(item.get("axes", {})) > doc["sq_generation"]["maximum_sensitive_parameters"]:
            raise ValueError(f"too many sensitive axes: {item['hypothesis_id']}")
        if item.get("priority_weight", 0) <= 0:
            raise ValueError(f"invalid priority: {item['hypothesis_id']}")

    generation = doc["sq_generation"]
    generation_size = generation["islands"] * generation["population_per_island"]
    budgets = [item.get("evaluation_budget", 0) for item in spaces]
    if any(budget <= 0 or budget % generation_size for budget in budgets):
        raise ValueError("hypothesis evaluation budget must contain whole generations")
    if any(budget > generation["maximum_evaluations_per_hypothesis"] for budget in budgets):
        raise ValueError("per-hypothesis evaluation budget exceeds cap")
    if max(budgets) // generation_size > generation["generations_max"]:
        raise ValueError("hypothesis evaluation budget exceeds generation cap")
    if sum(budgets) != generation["maximum_evaluations_global"]:
        raise ValueError("global evaluation budget mismatch")
    stopping = doc["stopping_policy"]
    if stopping["accepted_candidates_max_per_hypothesis"] * len(spaces) != stopping["accepted_candidates_max_global"]:
        raise ValueError("accepted-candidate budget mismatch")
    if stopping.get("no_budget_extension_after_performance") is not True:
        raise ValueError("budget extension must be forbidden")

    common_cost = doc["cost_policy"]
    if common_cost.get("leverage_cannot_rescue_negative_unlevered_expectancy") is not True:
        raise ValueError("unlevered edge invariant missing")
    if doc["capital"].get("research_leverage") != 1:
        raise ValueError("research must start at 1x")
    if doc["authorization"].get("paper_authorized") or doc["authorization"].get("live_authorized"):
        raise ValueError("paper/live must remain blocked")

    return {
        "decision": "PASS_NONCRYPTO_CAMPAIGN_PREREGISTRATION",
        "campaign_id": doc["campaign_id"],
        "preregistration_sha256": _hash(path),
        "hypothesis_count": catalog_result["hypothesis_count"],
        "maximum_evaluations_global": generation["maximum_evaluations_global"],
        "maximum_accepted_candidates": stopping["accepted_candidates_max_global"],
        "maximum_holdout_candidates": doc["holdout_policy"]["maximum_candidates_global"],
        "performance_accessed": False,
        "holdout_accessed": False,
        "sqcli_executed": False,
        "paper_authorized": False,
        "live_authorized": False
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
