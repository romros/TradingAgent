#!/usr/bin/env python3
"""Compile the frozen CAT D1 trend/pullback density pilot."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from lab.sq_bridge.alquimia_project import build

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_suffix(".json")
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def _epoch(value: str) -> str:
    return str(int(datetime.combine(date.fromisoformat(value), datetime.min.time(),
                                    tzinfo=timezone.utc).timestamp() * 1000))


def compile_pilot(output_dir: Path, spec_path: Path = SPEC) -> dict:
    spec = json.loads(spec_path.read_text())
    if spec["performance_accessed_before_freeze"] or spec["promotion_allowed"] or spec["volume_rules_allowed"]:
        raise ValueError("CAT pilot must remain blind, price-only and non-promotable")
    periods = spec["periods"]
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = {"markets": {"CAT": {
        "research_eligible": True, "sq_symbol": spec["sq_symbol"],
        "discovery_timeframe": "D1", "discovery_slippage": 0,
        "discovery_commission_per_order": 0,
        "sq_resource_clone_from": "BTCUSD_ALQ_H4", "sq_prune_resources": True,
        "sq_resource_remove_attributes": ["cloneFrom", "sourceTimezone"],
        "sq_resource_attributes": {"source": "1", "barType": "1", "precision": "D1",
            "timezone": "America/New_York", "dateFrom": _epoch(periods["train_from"]),
            "dateTo": _epoch(periods["untouched_future_to"]), "uSymbol": "CAT_IBKR_V2",
            "uSymbolName": "CAT_IBKR_V2", "removeWeekends": "false", "broker": "-1"},
        "sq_instrument_attributes": {"instrument": "CAT_IBKR_V2",
            "description": "CAT NYSE RTH D1 gross research", "tickSize": "0.001",
            "tickStep": "0.001", "minDistance": "0", "tickValueInMoney": "0",
            "dateFrom": "0", "dateTo": "0", "rows": "0", "totalDays": "0",
            "defaultSpread": "0", "defaultSlippage": "0", "decimals": "3",
            "commissions": "", "pointValue": "1", "dataType": "1",
            "recognizedFromOrders": "false", "exchange": "NYSE", "country": "US",
            "sector": "Industrials", "swap": "", "orderSizeMultiplier": "1",
            "orderSizeStep": "1", "broker": "-1"},
        "exit_at_end_of_day": False, "eod_exit_seconds": None,
        "signal_time_range_seconds": None, "exit_at_end_of_range": False,
        "maximum_trades_per_day": 1, "venue_max_leverage": 1}}}
    registry_path = output_dir / "frozen_market_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    methodology = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    methodology["methodology_id"] = spec["campaign_id"]
    methodology["capital_usdc"] = 1000
    methodology["small_account"]["canonical_capital_usdc"] = 1000
    # Schema-v4 builders read hypothesis_screen, not the legacy discovery
    # section.  Override both so the compiled SQ filter matches the frozen
    # CAT pilot instead of inheriting the portfolio-wide 250-trade gate.
    for gate_name in ("hypothesis_screen", "discovery"):
        if gate_name not in methodology:
            continue
        methodology[gate_name]["minimum_trades_train"] = spec["discovery"]["minimum_train_trades"]
        methodology[gate_name]["minimum_profit_factor_train"] = spec["discovery"]["minimum_profit_factor_train"]
    methodology_path = output_dir / "frozen_methodology.json"
    methodology_path.write_text(json.dumps(methodology, indent=2, sort_keys=True) + "\n")
    explicit = {"train_from": periods["train_from"], "train_to": periods["train_to"],
        "validation_from": periods["validation_from"], "validation_to": periods["validation_to"],
        "oos_from": periods["sealed_oos_from"], "oos_to": periods["sealed_oos_to"],
        "holdout_from": periods["untouched_future_from"], "holdout_to": periods["untouched_future_to"]}
    cfx = output_dir / "project.cfx"
    manifest = build(SCAFFOLD, cfx, "IBKR_V2_CAT_D1_TREND_PULLBACK_DENSITY_V2", "CAT",
        registry_path, methodology_path, date.fromisoformat(explicit["train_from"]),
        date.fromisoformat(explicit["holdout_to"]), spec["discovery"]["accepted_limit"],
        spec["discovery"]["search_profile"], spec["discovery"]["generation"],
        spec["discovery"]["attempt_budget"], spec["discovery"]["wall_time_budget_minutes"],
        None, spec["discovery"]["direction"], periods_override=explicit)
    receipt = {"decision": "PASS_THEORETICAL_DENSITY_PILOT_READY", "project": str(cfx),
        "manifest": str(cfx.with_suffix(".manifest.json")), "project_sha256": manifest["output_sha256"],
        "promotion_allowed": False, "paper_authorized": False, "live_authorized": False}
    (output_dir / "compile_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    print(json.dumps(compile_pilot(ROOT / "data/ibkr_sq_v2/cat_d1_trend_pilot"), indent=2))
