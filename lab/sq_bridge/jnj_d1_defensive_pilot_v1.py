#!/usr/bin/env python3
"""Compile the frozen JNJ D1 defensive trend/pullback discovery campaign."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from lab.sq_bridge.alquimia_project import build


ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_suffix(".json")
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def epoch(value: str) -> str:
    point = datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)
    return str(int(point.timestamp() * 1000))


def compile_pilot(output_dir: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    periods = spec["periods"]
    if spec["performance_accessed_before_freeze"] or spec["promotion_allowed"]:
        raise ValueError("JNJ campaign must remain blind and non-promotable")
    roundtrip = json.loads((ROOT / spec["roundtrip_receipt"]).read_text())
    if roundtrip["decision"] != "PASS_SIGNAL_RESEARCH" or not roundtrip["timestamps_exact_and_ordered"]:
        raise ValueError("JNJ SQ roundtrip gate did not pass")
    for field in ("open", "high", "low", "close"):
        if roundtrip["field_errors"][field]["changed_rows"] != 0:
            raise ValueError(f"JNJ SQ roundtrip changed {field}")
    output_dir.mkdir(parents=True, exist_ok=True)
    symbol = spec["sq_symbol"]
    registry = {"markets": {"JNJ": {
        "research_eligible": True, "sq_symbol": symbol, "discovery_timeframe": "D1",
        "discovery_slippage": 0, "discovery_commission_per_order": 0,
        "sq_resource_clone_from": "BTCUSD_ALQ_H4", "sq_prune_resources": True,
        "sq_resource_remove_attributes": ["cloneFrom", "sourceTimezone"],
        "sq_resource_attributes": {
            "source": "1", "barType": "1", "precision": "D1", "timezone": "America/New_York",
            "dateFrom": epoch(periods["train_from"]), "dateTo": epoch(periods["sealed_oos_to"]),
            "uSymbol": "JNJ_IBKR_V2", "uSymbolName": "JNJ_IBKR_V2", "removeWeekends": "false",
            "broker": "-1"
        },
        "sq_instrument_attributes": {
            "instrument": "JNJ_IBKR_V2", "description": "JNJ NYSE D1 theoretical research",
            "tickSize": "0.001", "tickStep": "0.001", "minDistance": "0", "tickValueInMoney": "0",
            "dateFrom": "0", "dateTo": "0", "rows": "0", "totalDays": "0", "defaultSpread": "0",
            "defaultSlippage": "0", "decimals": "3", "commissions": "", "pointValue": "1",
            "dataType": "1", "recognizedFromOrders": "false", "exchange": "NYSE", "country": "US",
            "sector": "Healthcare", "swap": "", "orderSizeMultiplier": "1", "orderSizeStep": "1",
            "broker": "-1"
        },
        "exit_at_end_of_day": False, "eod_exit_seconds": None, "signal_time_range_seconds": None,
        "exit_at_end_of_range": False, "maximum_trades_per_day": 1, "venue_max_leverage": 1
    }}}
    registry_path = output_dir / "frozen_market_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    method = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    method["methodology_id"] = spec["campaign_id"]
    method["capital_usdc"] = 1000
    method["small_account"]["canonical_capital_usdc"] = 1000
    for key in ("hypothesis_screen", "discovery"):
        if key in method:
            method[key]["minimum_trades_train"] = spec["discovery"]["minimum_train_trades"]
            method[key]["minimum_profit_factor_train"] = spec["discovery"]["minimum_profit_factor_train"]
    methodology = output_dir / "frozen_methodology.json"
    methodology.write_text(json.dumps(method, indent=2, sort_keys=True) + "\n")
    explicit = {
        "train_from": periods["train_from"], "train_to": periods["train_to"],
        "validation_from": periods["validation_from"], "validation_to": periods["validation_to"],
        "oos_from": periods["sealed_oos_from"], "oos_to": periods["sealed_oos_to"],
        "holdout_from": periods["untouched_future_from"], "holdout_to": periods["untouched_future_to"]
    }
    cfx = output_dir / "project.cfx"
    manifest = build(
        SCAFFOLD, cfx, "IBKR_V2_JNJ_D1_DEFENSIVE_V1", "JNJ", registry_path, methodology,
        date.fromisoformat(explicit["train_from"]), date.fromisoformat(explicit["holdout_to"]),
        spec["discovery"]["accepted_limit"], spec["discovery"]["search_profile"],
        spec["discovery"]["generation"], spec["discovery"]["attempt_budget"],
        spec["discovery"]["wall_time_budget_minutes"], None, spec["discovery"]["direction"],
        periods_override=explicit
    )
    receipt = {
        "decision": "PASS_THEORETICAL_DISCOVERY_READY", "project": str(cfx),
        "manifest": str(cfx.with_suffix(".manifest.json")), "project_sha256": manifest["output_sha256"],
        "promotion_allowed": False, "paper_authorized": False, "live_authorized": False
    }
    (output_dir / "compile_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    print(json.dumps(compile_pilot(ROOT / "data/ibkr_sq_v2/jnj_d1_defensive_pilot"), indent=2))
