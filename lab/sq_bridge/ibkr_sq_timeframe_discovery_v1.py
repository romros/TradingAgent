#!/usr/bin/env python3
"""Compile cost-aware IBUS500 SQ discovery batches for the D1-down funnel."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from lab.sq_bridge.alquimia_project import build
from lab.sq_bridge.sq_project_contract import verify_genetic_project

ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


PROFILED_D1_FAMILIES = {
    "momentum": "us500_d1_time_series_momentum_v4",
    "shock_reversion": "us500_d1_shock_reversion_v4",
    "volatility_trend": "us500_d1_volatility_regime_trend_v4",
}


def compile_batch(timeframe: str, output_dir: Path, version: int,
                  lane: str = "exploratory") -> dict:
    if timeframe not in {"D1", "H1", "M30"} or version < 1:
        raise ValueError("unsupported timeframe/version")
    if lane not in {"exploratory", "profiled"}:
        raise ValueError("unsupported discovery lane")
    if lane == "profiled" and timeframe != "D1":
        raise ValueError("profiled v1 is preregistered for D1 only")
    prereg = ROOT / "lab/sq_bridge/ibkr_aggressive_preregistration_v1.json"
    spec = json.loads(prereg.read_text())
    source_registry = ROOT / "lab/sq_bridge/ibkr_sq_markets_v1.json"
    registry = json.loads(source_registry.read_text())
    market = registry["markets"]["IBUS500"]
    market["discovery_timeframe"] = timeframe
    if timeframe == "D1":
        # Use the already round-trip-certified regular-session daily resource.
        # The M1 UTC resource is appropriate for intraday work, not for defining
        # a US exchange day across daylight-saving transitions.
        market.update({
            "sq_symbol": "US500_ALQ_RTH_D1",
            # Clone the only resource node present in the format-only scaffold;
            # every scientific attribute is overwritten immediately below.
            "sq_resource_clone_from": "BTCUSD_ALQ_H4",
            "sq_resource_attributes": {
                "source": "3", "barType": "1", "precision": "D1",
                "timezone": "Etc/UTC", "dateFrom": "1514937600000",
                "dateTo": "1783468800000", "uSymbol": "US500_ALQ_RTH",
                "uSymbolName": "US500_ALQ_RTH", "removeWeekends": "false",
                "broker": "-1",
            },
            "sq_instrument_attributes": {
                "instrument": "US500_ALQ", "description": "Alquimia_US500_RTH_signal_research",
                "tickSize": "0.001", "tickStep": "0.001", "minDistance": "0.0",
                "tickValueInMoney": "0.0", "dateFrom": "0", "dateTo": "0",
                "rows": "0", "totalDays": "0", "defaultSpread": "0",
                "defaultSlippage": "0", "decimals": "3", "commissions": "",
                "pointValue": "1.0", "dataType": "6", "recognizedFromOrders": "false",
                "exchange": "", "country": "", "sector": "", "swap": "",
                "orderSizeMultiplier": "1.0", "orderSizeStep": "0.01", "broker": "-1",
            },
            "exit_at_end_of_day": False,
            "eod_exit_seconds": None,
            "signal_time_range_seconds": None,
            "exit_at_end_of_range": False,
            "timezone_caveat": "Certified US regular-session D1 resource; descend to intraday only with DST-aware sessions.",
        })
    registry_path = output_dir / "frozen_market_registry.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    scaffold = Path("/mnt/volume-SQ/user/projects/ALQUIMIA_CRYPTO_H4_CFX_SMOKE_V2/project.cfx")
    methodology = ROOT / "lab/sq_bridge/methodology_ibkr_sq_v1.json"
    if timeframe == "D1":
        method = json.loads(methodology.read_text())
        method["methodology_id"] = "ibkr-sq-aggressive-d1-funnel-v1"
        method["discovery"]["minimum_trades_train"] = 60
        method["temporal_validation"]["minimum_trades_oos"] = 20
        methodology = output_dir / "frozen_methodology.json"
        methodology.write_text(json.dumps(method, indent=2, sort_keys=True) + "\n")
    projects = {}
    jobs = ([("generic", side, "generic_translatable")
             for side in ("long", "short", "both")]
            if lane == "exploratory" else
            [(family, side, profile)
             for family, profile in PROFILED_D1_FAMILIES.items()
             for side in ("long", "short")])
    date_from = date(2018, 1, 3) if timeframe == "D1" else date(2012, 1, 19)
    date_to = date(2026, 7, 8) if timeframe == "D1" else date(2025, 12, 31)
    for family, side, profile in jobs:
        hypothesis = f"ibus500_{timeframe.lower()}_{lane}_{family}_{side}_v{version}"
        project_name = f"IBKR_IBUS500_{timeframe}_{lane.upper()}_{family.upper()}_{side.upper()}_V{version}"
        cfx = output_dir / hypothesis / "project.cfx"
        manifest = build(scaffold, cfx, project_name, "IBUS500", registry_path,
                         methodology, date_from, date_to, 20,
                         profile, "genetic-evolution", 10000,
                         120, None, side)
        shape = verify_genetic_project(cfx, manifest)
        projects[hypothesis] = {
            "project_name": project_name, "project_cfx_path": str(cfx.resolve()),
            "project_cfx_sha256": sha(cfx),
            "project_manifest_path": str(cfx.with_suffix('.manifest.json').resolve()),
            "project_manifest_sha256": sha(cfx.with_suffix('.manifest.json')),
            "sq_genetic_shape": shape,
        }
    result = {"schema_version": 1, "decision": "PASS_CFX_BATCH_READY",
              "campaign_id": spec["campaign_id"], "timeframe": timeframe,
              "discovery_lane": lane,
              "preregistration_path": str(prereg.resolve()),
              "preregistration_sha256": sha(prereg), "projects": projects,
              "selected_hypothesis_ids": sorted(projects), "sqcli_started": False,
              "paper_authorized": False, "live_authorized": False}
    (output_dir / "project_batch.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeframe", choices=("D1", "H1", "M30"), required=True)
    parser.add_argument("--lane", choices=("exploratory", "profiled"),
                        default="exploratory")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = compile_batch(args.timeframe, args.output_dir, args.version, args.lane)
    print(json.dumps({"decision": result["decision"],
                      "projects": sorted(result["projects"])}, indent=2))


if __name__ == "__main__":
    main()
