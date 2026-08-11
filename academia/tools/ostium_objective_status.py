#!/usr/bin/env python3
"""Mostra si el treball actual acosta el catàleg Ostium al target x2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def status(objective: dict, catalog: dict) -> dict:
    active = objective["active_assets"]
    by_asset = {item["asset"]: item for item in catalog["assets"]}
    missing = [asset for asset in active if asset not in by_asset]
    components = sum(len(by_asset[asset]["promotable_components"]) for asset in active if asset in by_asset)
    component_target = objective["portfolio_components"]
    minimum_components = component_target["minimum_strategies"]
    maximum_components = component_target["maximum_strategies"]
    preferred_range = component_target["preferred_diversified_range"]
    rejected = sum(len(by_asset[asset]["rejected_families"]) for asset in active if asset in by_asset)
    ready_assets = [asset for asset in active if asset in by_asset and by_asset[asset]["promotable_components"]]
    next_actions = [
        {"asset": asset, "action": by_asset[asset]["next_action"]}
        for asset in active if asset in by_asset and not by_asset[asset]["promotable_components"]
    ]
    portfolio_ready = not missing and components >= minimum_components
    components_needed = max(0, minimum_components - components)
    return {
        "objective": objective["objective"],
        "target_is_promise": False,
        "catalog": {
            "active_assets": len(active),
            "promotable_components": components,
            "rejected_families": rejected,
            "assets_with_component": ready_assets,
            "strategy_target": [minimum_components, maximum_components],
            "preferred_diversified_range": preferred_range,
            "strategies_needed_for_portfolio": components_needed,
            "asset_coverage_required": component_target["asset_coverage_required"],
        },
        "portfolio_ready": portfolio_ready,
        "x2_simulation_ready": portfolio_ready,
        "holdout": catalog["holdout_status"],
        "blocker": None if portfolio_ready else "falta almenys una família neta promocionable; el nombre final entre 1 i 6 es decidirà per millora marginal de retorn i supervivència",
        "next_actions": next_actions,
        "missing_assets": missing,
    }


def task_gate(objective: dict, task: dict) -> dict:
    errors = []
    if task.get("contribution") not in objective["allowed_work"]:
        errors.append("contribution_outside_objective")
    asset = task.get("asset")
    if asset is not None and asset not in objective["active_assets"]:
        errors.append("asset_outside_active_universe")
    if not task.get("expected_decision"):
        errors.append("missing_expected_decision")
    if not task.get("stop_condition"):
        errors.append("missing_stop_condition")
    if task.get("uses_holdout"):
        errors.append("premature_holdout_use")
    return {"aligned": not errors, "errors": errors, "task": task.get("id", "unknown")}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--objective", type=Path, default=root / "packages/strategyquant/ostium-500-objective.json")
    parser.add_argument("--catalog", type=Path, default=root / "packages/strategyquant/ostium-500-strategy-catalog.json")
    parser.add_argument("--task", type=Path)
    args = parser.parse_args()
    objective = json.loads(args.objective.read_text())
    if args.task:
        result = task_gate(objective, json.loads(args.task.read_text()))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["aligned"] else 1
    catalog = json.loads(args.catalog.read_text())
    print(json.dumps(status(objective, catalog), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
