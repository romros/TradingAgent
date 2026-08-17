#!/usr/bin/env python3
"""Compile the preregistered PEP discovery side of the PEP/KO campaign."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from lab.sq_bridge.alquimia_project import build

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name("pep_ko_d1_trend_pullback_v1.json")
LOCK = Path(__file__).with_name("pep_ko_d1_trend_pullback_v1.lock.json")
SOURCE = ROOT / "data/ibkr_sq_v2/preflight/PEPUSUSD_CANONICAL_D1_2017_2024.csv"
REPORT = ROOT / "data/ibkr_sq_v2/preflight/pep_canonical_source_2017_2024.json"
SCAFFOLD = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def epoch(value: str) -> str:
    moment = datetime.combine(date.fromisoformat(value), datetime.min.time(),
                              tzinfo=timezone.utc)
    return str(int(moment.timestamp() * 1000))


def compile_campaign(output: Path) -> dict:
    spec, lock, report = (json.loads(path.read_text())
                          for path in (SPEC, LOCK, REPORT))
    if (sha(SPEC) != lock["spec_sha256"]
            or sha(SOURCE) != lock["pep_source_sha256"]
            or spec["performance_accessed_for_this_family"]
            or not report["decision"].startswith("PASS")):
        raise ValueError("frozen blind PEP source contract failed")
    with SOURCE.open(newline="") as stream:
        rows = list(csv.reader(stream))
    if (len(rows) != 1800 or rows[0][0] != "2017.11.02"
            or rows[-1][0] != "2024.12.31"
            or any(row[0] > "2024.12.31" for row in rows)):
        raise ValueError("PEP canonical boundary mismatch")
    output.mkdir(parents=True, exist_ok=True)
    imported = output / "PEPUSUSD_NYSE_RTH_D1_2017_2024_MT4.csv"
    imported.write_bytes(SOURCE.read_bytes())
    periods, discovery = spec["periods"], spec["discovery"]
    instrument = "PEP_IBKR_TREND_PULLBACK_V1"
    registry = {"markets": {"PEP": {
        "research_eligible": True,
        "sq_symbol": spec["discovery_asset"]["sq_symbol"],
        "discovery_timeframe": "D1", "discovery_slippage": 0,
        "discovery_commission_per_order": 0,
        "sq_resource_clone_from": "BTCUSD_ALQ_H4", "sq_prune_resources": True,
        "sq_resource_remove_attributes": ["cloneFrom", "sourceTimezone"],
        "sq_resource_attributes": {
            "source": "1", "barType": "1", "precision": "D1",
            "timezone": "America/New_York", "dateFrom": epoch(periods["train_from"]),
            "dateTo": epoch(periods["sealed_oos_to"]), "uSymbol": instrument,
            "uSymbolName": instrument, "removeWeekends": "false", "broker": "-1"},
        "sq_instrument_attributes": {
            "instrument": instrument, "description": "PEP D1 trend pullback research",
            "tickSize": "0.001", "tickStep": "0.001", "minDistance": "0",
            "tickValueInMoney": "0", "dateFrom": "0", "dateTo": "0",
            "rows": "0", "totalDays": "0", "defaultSpread": "0",
            "defaultSlippage": "0", "decimals": "3", "commissions": "",
            "pointValue": "1", "dataType": "1", "recognizedFromOrders": "false",
            "exchange": "NASDAQ", "country": "US", "sector": "Consumer Staples",
            "swap": "", "orderSizeMultiplier": "1", "orderSizeStep": "1",
            "broker": "-1"},
        "exit_at_end_of_day": False, "eod_exit_seconds": None,
        "signal_time_range_seconds": None, "exit_at_end_of_range": False,
        "maximum_trades_per_day": 1, "venue_max_leverage": 1}}}
    registry_path = output / "frozen_market_registry.json"
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    methodology = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    methodology["methodology_id"] = spec["campaign_id"]
    methodology["capital_usdc"] = 1000
    methodology["small_account"]["canonical_capital_usdc"] = 1000
    methodology["discovery"].update({
        "max_rules": discovery["maximum_entry_rules"],
        "minimum_trades_train": discovery["minimum_train_trades"],
        "minimum_profit_factor_train": discovery["minimum_profit_factor_train"]})
    methodology_path = output / "frozen_methodology.json"
    methodology_path.write_text(json.dumps(methodology, indent=2, sort_keys=True) + "\n")
    split = {
        "train_from": periods["train_from"], "train_to": periods["train_to"],
        "validation_from": periods["validation_from"], "validation_to": periods["validation_to"],
        "oos_from": periods["sealed_oos_from"], "oos_to": periods["sealed_oos_to"],
        "holdout_from": "2025-01-02", "holdout_to": "2025-12-31"}
    project = output / "project.cfx"
    manifest = build(
        SCAFFOLD, project, "IBKR_PEP_D1_TREND_PULLBACK_V1", "PEP",
        registry_path, methodology_path, date.fromisoformat(periods["train_from"]),
        date(2025, 12, 31), discovery["accepted_limit"], discovery["search_profile"],
        discovery["generation"], discovery["attempt_budget"],
        discovery["wall_time_budget_minutes"], None, discovery["direction"],
        periods_override=split)
    result = {
        "decision": "PASS_PEP_DISCOVERY_READY",
        "project_sha256": manifest["output_sha256"], "source_rows": len(rows),
        "source_sha256": sha(SOURCE), "spec_sha256": sha(SPEC),
        "performance_accessed": False, "sqcli_started": False,
        "holdout_2025_accessed": False, "paper_authorized": False,
        "live_authorized": False}
    (output / "compile_receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    print(json.dumps(compile_campaign(
        ROOT / "data/ibkr_sq_v2/pep_ko_d1_trend_pullback_v1"), indent=2))


if __name__ == "__main__":
    main()
