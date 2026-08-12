#!/usr/bin/env python3
"""Compile preregistered direct SPY D1 discovery with one-share economics."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build
from lab.sq_bridge.sq_project_contract import verify_genetic_project

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_batch(output_dir: Path, version: int = 1) -> dict:
    if version < 1:
        raise ValueError("VERSION_INVALID")
    output_dir.mkdir(parents=True, exist_ok=True)
    methodology = json.loads((ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json").read_text())
    methodology.update({"methodology_id": "ibkr-spy-d1-direct-cost-aware-v1"})
    methodology["discovery"].update({
        "minimum_trades_train": 60, "minimum_profit_factor_train": 1.20,
    })
    methodology["temporal_validation"]["minimum_trades_oos"] = 20
    method_path = output_dir / "frozen_methodology.json"
    method_path.write_text(json.dumps(methodology, indent=2, sort_keys=True) + "\n")
    market = {
        "markets": {"SPY_SHARE_CFD_PROXY": {
            "status": "SQ_PROPRIETARY_QUARANTINE",
            "research_eligible": True,
            "sq_symbol": "SPY_benchmark.D", "discovery_timeframe": "D1",
            "sq_resource_clone_from": "BTCUSD_ALQ_H4",
            "sq_resource_attributes": {
                "source": "3", "barType": "1", "precision": "D1",
                "timezone": "America/New_York", "uSymbol": "SPY_benchmark",
                "uSymbolName": "SPY_benchmark", "removeWeekends": "true",
                "broker": "-1",
            },
            "sq_instrument_attributes": {
                "instrument": "SPY_benchmark", "description": "History data instrument",
                "tickSize": "0.01", "tickStep": "0.01", "minDistance": "0",
                "tickValueInMoney": "0", "dateFrom": "0", "dateTo": "0",
                "rows": "0", "totalDays": "0", "defaultSpread": "0",
                "defaultSlippage": "0", "decimals": "2", "commissions": "",
                "pointValue": "1.0", "dataType": "6", "recognizedFromOrders": "false",
                "exchange": "", "country": "", "sector": "", "swap": "",
                "orderSizeMultiplier": "1", "orderSizeStep": "1", "broker": "-1",
            },
            "sq_prune_resources": True, "discovery_commission_per_order": 2.0,
            "discovery_slippage": 0,
            "maximum_trades_per_day": 1, "exit_at_end_of_day": False,
            "exit_at_end_of_range": False,
        }},
        "source_classification": "SQ_PROPRIETARY_QUARANTINE",
        "ibkr_contract_verified": False,
    }
    registry = output_dir / "frozen_market_registry.json"
    registry.write_text(json.dumps(market, indent=2, sort_keys=True) + "\n")
    scaffold = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")
    jobs = {"generic": "generic_translatable",
            "volatility_trend": "us500_d1_volatility_regime_trend_v4"}
    projects = {}
    for family, profile in jobs.items():
        hypothesis = f"spy_d1_direct_{family}_long_v{version}"
        name = f"IBKR_SPY_D1_DIRECT_{family.upper()}_LONG_V{version}"
        cfx = output_dir / hypothesis / "project.cfx"
        manifest = build(scaffold, cfx, name, "SPY_SHARE_CFD_PROXY", registry,
                         method_path, date(2018, 1, 3), date(2026, 7, 8), 20,
                         profile, "genetic-evolution", 10000, 120, None, "long")
        projects[hypothesis] = {
            "project_name": name, "project_cfx_path": str(cfx.resolve()),
            "project_cfx_sha256": digest(cfx),
            "project_manifest_path": str(cfx.with_suffix(".manifest.json").resolve()),
            "project_manifest_sha256": digest(cfx.with_suffix(".manifest.json")),
            "sq_genetic_shape": verify_genetic_project(cfx, manifest),
        }
    result = {"schema_version": 1, "decision": "PASS_CFX_BATCH_READY",
              "campaign_type": "SPY_DIRECT_COST_AWARE",
              "preregistered_before_performance": True,
              "commission_round_trip_usd": 2.0, "fixed_size_shares": 1,
              "holdout_accessed": False, "projects": projects,
              "selected_hypothesis_ids": sorted(projects),
              "sqcli_started": False, "paper_authorized": False,
              "live_authorized": False}
    (output_dir / "project_batch.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(compile_batch(args.output_dir, args.version), indent=2))


if __name__ == "__main__":
    main()
