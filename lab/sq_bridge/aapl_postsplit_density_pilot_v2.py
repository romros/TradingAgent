#!/usr/bin/env python3
"""Compile a fresh, non-promotable AAPL post-split SQ density pilot."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build


ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_suffix(".json")
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def compile_pilot(output_dir: Path, *, spec_path: Path = SPEC,
                  project_name: str = "IBKR_V2_AAPL_D1_POSTSPLIT_DENSITY") -> dict:
    spec = json.loads(spec_path.read_text())
    if spec["promotion_allowed"] or spec["performance_accessed_before_freeze"]:
        raise ValueError("AAPL density pilot must remain blind and non-promotable")
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = {"markets": {"AAPL": {
        "research_eligible": True,
        "sq_symbol": "AAPLUSUSD",
        "discovery_timeframe": "D1",
        "discovery_slippage": 0,
        "discovery_commission_per_order": float(
            spec["discovery"].get("commission_per_order_usd", 1.0)),
        "sq_resource_clone_from": "BTCUSD_ALQ_H4",
        "sq_prune_resources": True,
        "sq_resource_remove_attributes": ["cloneFrom", "sourceTimezone"],
        "sq_resource_attributes": {
            "source": "2", "barType": "1", "precision": "D1",
            "timezone": "America/New_York", "dateFrom": "1598832000000",
            "dateTo": "1735603200000", "uSymbol": "AAPLUSUSD",
            "uSymbolName": "APPLE INC", "removeWeekends": "false", "broker": "-1"
        },
        "sq_instrument_attributes": {
            "instrument": "AAPLUSUSD", "description": "Dukascopy AAPL post-split density pilot",
            "tickSize": "0.01", "tickStep": "0.01", "minDistance": "0.0",
            "tickValueInMoney": "0.0", "dateFrom": "0", "dateTo": "0",
            "rows": "0", "totalDays": "0", "defaultSpread": "0",
            "defaultSlippage": "0", "decimals": "2", "commissions": "",
            "pointValue": "1.0", "dataType": "1", "recognizedFromOrders": "false",
            "exchange": "NASDAQ", "country": "US", "sector": "Technology",
            "swap": "", "orderSizeMultiplier": "1.0", "orderSizeStep": "1.0", "broker": "-1"
        },
        "exit_at_end_of_day": False,
        "eod_exit_seconds": None,
        "signal_time_range_seconds": None,
        "exit_at_end_of_range": False,
        "maximum_trades_per_day": 1,
        "venue_max_leverage": 1
    }}}
    registry_path = output_dir / "frozen_market_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    methodology = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    methodology["methodology_id"] = "ibkr-v2-aapl-postsplit-density-pilot"
    methodology["capital_usdc"] = 1000
    methodology["discovery"]["minimum_trades_train"] = spec["discovery"]["minimum_train_trades"]
    methodology["discovery"]["minimum_profit_factor_train"] = spec["discovery"].get(
        "minimum_profit_factor_train", methodology["discovery"]["minimum_profit_factor_train"])
    methodology["small_account"]["capital_scenarios_usdc"] = [200, 400, 500, 700, 1000, 2000]
    methodology["small_account"]["canonical_capital_usdc"] = 1000
    methodology_path = output_dir / "frozen_methodology.json"
    methodology_path.write_text(json.dumps(methodology, indent=2, sort_keys=True) + "\n")
    timeframe = spec["discovery"]["timeframe"]
    if timeframe not in {"D1", "H4", "H1"}:
        raise ValueError("unsupported AAPL pilot timeframe")
    market = registry["markets"]["AAPL"]
    market["discovery_timeframe"] = timeframe
    if timeframe in {"H4", "H1"}:
        market["sq_symbol"] = "AAPLUSUSD_TICK_UTCMinus05"
        market["sq_resource_attributes"].update({
            "precision": "TICK", "uSymbol": "AAPLUSUSD",
            "uSymbolName": "APPLE INC", "source": "2",
        })
        registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    cfx = output_dir / "project.cfx"
    periods = spec["periods"]
    explicit_periods = {
        "train_from": periods["train_from"],
        "train_to": periods["train_to"],
        "validation_from": periods["validation_from"],
        "validation_to": periods["validation_to"],
        "oos_from": periods["sealed_oos_from"],
        "oos_to": periods["sealed_oos_to"],
        "holdout_from": periods["untouched_future_from"],
        "holdout_to": periods.get("untouched_future_to", "2025-12-31"),
    }
    manifest = build(
        SCAFFOLD, cfx, project_name, "AAPL",
        registry_path, methodology_path,
        date.fromisoformat(explicit_periods["train_from"]),
        date.fromisoformat(explicit_periods["holdout_to"]),
        spec["discovery"]["accepted_limit"],
        spec["discovery"].get("search_profile", "generic_translatable"),
        spec["discovery"]["generation"], spec["discovery"]["attempt_budget"],
        spec["discovery"]["wall_time_budget_minutes"], None,
        spec["discovery"]["direction"], periods_override=explicit_periods)
    if manifest.get("generation_type") != spec["discovery"]["generation"]:
        raise ValueError("AAPL pilot generation type drifted from its frozen spec")
    receipt = {"decision": "PASS_NON_PROMOTABLE_PILOT_READY", "project": str(cfx),
               "manifest": str(cfx.with_suffix('.manifest.json')),
               "promotion_allowed": False, "paper_authorized": False, "live_authorized": False}
    (output_dir / "compile_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


if __name__ == "__main__":
    print(json.dumps(compile_pilot(ROOT / "data/ibkr_sq_v2/aapl_density_pilot"), indent=2))
