#!/usr/bin/env python3
"""Compile the blind EEM D1 discovery project and frozen adjusted source."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from lab.sq_bridge.alquimia_project import build

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name("eem_d1_discovery_v1.json")
SOURCE = ROOT / "data/ibkr_sq_v2/etf_twelve_one_momentum_v1/adjusted/EEM_ADJUSTED_D1_2017_2024.csv"
SOURCE_SHA256 = "3ec5b1bb028a35add08412dc990ed230f5b467c271cb4106b2f008c0636ddc54"
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def epoch(value: str) -> str:
    moment = datetime.combine(date.fromisoformat(value), datetime.min.time(), tzinfo=timezone.utc)
    return str(int(moment.timestamp() * 1000))


def compile_campaign(output: Path) -> dict:
    spec = json.loads(SPEC.read_text())
    rows = list(csv.DictReader(SOURCE.open(newline="")))
    if (sha(SOURCE) != SOURCE_SHA256 or rows[0]["date"] != "2017-01-03"
            or rows[-1]["date"] != "2024-12-31"):
        raise ValueError("frozen EEM source mismatch")
    if any(row["date"] > "2024-12-31" for row in rows):
        raise ValueError("post-2024 row refused")
    output.mkdir(parents=True, exist_ok=True)
    mt4 = output / "EEM_ADJUSTED_D1_2017_2024_MT4.csv"
    with mt4.open("w", newline="") as stream:
        writer = csv.writer(stream)
        for row in rows:
            writer.writerow([row["date"].replace("-", "."), "00:00", row["open"],
                             row["high"], row["low"], row["close"], 0])

    periods, discovery = spec["periods"], spec["discovery"]
    market = {
        "research_eligible": True,
        "sq_symbol": spec["sq_symbol"],
        "discovery_timeframe": "D1",
        "discovery_slippage": 0,
        "discovery_commission_per_order": 0,
        "sq_resource_clone_from": "BTCUSD_ALQ_H4",
        "sq_prune_resources": True,
        "sq_resource_remove_attributes": ["cloneFrom", "sourceTimezone"],
        "sq_resource_attributes": {
            "source": "1", "barType": "1", "precision": "D1",
            "timezone": "America/New_York", "dateFrom": epoch(periods["train_from"]),
            "dateTo": epoch(periods["sealed_oos_to"]), "uSymbol": "EEM_IBKR_D1_V1",
            "uSymbolName": "EEM_IBKR_D1_V1", "removeWeekends": "false", "broker": "-1"
        },
        "sq_instrument_attributes": {
            "instrument": "EEM_IBKR_D1_V1", "description": "EEM adjusted D1 research",
            "tickSize": "0.000001", "tickStep": "0.000001", "minDistance": "0",
            "tickValueInMoney": "0", "dateFrom": "0", "dateTo": "0", "rows": "0",
            "totalDays": "0", "defaultSpread": "0", "defaultSlippage": "0",
            "decimals": "6", "commissions": "", "pointValue": "1", "dataType": "1",
            "recognizedFromOrders": "false", "exchange": "NYSE Arca", "country": "US",
            "sector": "Emerging Markets", "swap": "", "orderSizeMultiplier": "1",
            "orderSizeStep": "1", "broker": "-1"
        },
        "exit_at_end_of_day": False, "eod_exit_seconds": None,
        "signal_time_range_seconds": None, "exit_at_end_of_range": False,
        "maximum_trades_per_day": 1, "venue_max_leverage": 1
    }
    registry = output / "frozen_market_registry.json"
    registry.write_text(json.dumps({"markets": {"EEM": market}}, indent=2, sort_keys=True) + "\n")
    methodology = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    methodology["methodology_id"] = spec["campaign_id"]
    methodology["capital_usdc"] = 1000
    methodology["small_account"]["canonical_capital_usdc"] = 1000
    for key in ("hypothesis_screen", "discovery"):
        if key in methodology:
            methodology[key]["minimum_trades_train"] = discovery["minimum_train_trades"]
            methodology[key]["minimum_profit_factor_train"] = discovery["minimum_profit_factor_train"]
    method_path = output / "frozen_methodology.json"
    method_path.write_text(json.dumps(methodology, indent=2, sort_keys=True) + "\n")
    override = {
        "train_from": periods["train_from"], "train_to": periods["train_to"],
        "validation_from": periods["validation_from"], "validation_to": periods["validation_to"],
        "oos_from": periods["sealed_oos_from"], "oos_to": periods["sealed_oos_to"],
        "holdout_from": "2025-01-02", "holdout_to": "2025-12-31"
    }
    manifest = build(
        SCAFFOLD, output / "project.cfx", "IBKR_EEM_D1_SIMPLE_DISCOVERY_V1", "EEM",
        registry, method_path, date.fromisoformat(periods["train_from"]), date(2025, 12, 31),
        discovery["accepted_limit"], discovery["search_profile"], discovery["generation"],
        discovery["attempt_budget"], discovery["wall_time_budget_minutes"], None,
        discovery["direction"], periods_override=override)
    result = {
        "decision": "PASS_EEM_D1_DISCOVERY_READY", "source_sha256": sha(SOURCE),
        "mt4_sha256": sha(mt4), "rows": len(rows),
        "project_sha256": manifest["output_sha256"], "performance_accessed": False,
        "sqcli_started": False, "paper_authorized": False, "live_authorized": False
    }
    (output / "compile_receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(compile_campaign(ROOT / "data/ibkr_sq_v2/eem_d1_simple_discovery_v1"), indent=2))
