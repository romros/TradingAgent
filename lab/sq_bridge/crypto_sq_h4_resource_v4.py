#!/usr/bin/env python3
"""Certify a neutral StrategyQuant H4 resource from an exact OHLC round trip."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lab.sq_bridge.crypto_h4_canonical_source_v4 import write_json_atomic
from lab.sq_bridge.sq_data_roundtrip_audit import audit


MARKETS = {
    "BTCUSD": {"campaign_id": "btcusd-h4-alquimia-v4",
               "source_symbol": "BTCUSDT", "sq_symbol": "BTCUSD_ALQ_H4",
               "instrument": "BTC_ALQ", "order_size_step": .0001,
               "first": "2018.03.01", "last": "2026.06.30"},
    "ETHUSD": {"campaign_id": "ethusd-h4-alquimia-v4",
               "source_symbol": "ETHUSDT", "sq_symbol": "ETHUSD_ALQ_H4",
               "instrument": "ETH_ALQ", "order_size_step": .001,
               "first": "2019.01.01", "last": "2026.06.30"},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def expected_commands(market: str, host_source: Path, host_export_dir: Path) -> list[str]:
    spec = MARKETS[market]
    slug = market.lower()
    container_source = f"/home/squser/SQ/user/imports/alquimia_crypto_v4/{market}_ALQ_H4.csv"
    container_export = (f"/home/squser/SQ/user/exports/alquimia_crypto_v4_"
                        f"{market[:3].lower()}_h4_roundtrip")
    return [
        (f"-instrument action=add instrument={spec['instrument']} "
         f"description=Alquimia_{market}_H4_gross_signal_research pointvalue=1 "
         f"ticksize=0.01 tickstep=0.01 defaultspread=0 datatype=crypto "
         f"orderSizeMultiplier=1 orderSizeStep={spec['order_size_step']}"),
        (f"-symbol action=add symbols={market}_ALQ instrument={spec['instrument']} "
         "datasource=file datatype=H4 postfix=_H4 exchange=Alquimia"),
        (f"-data action=import symbol={spec['sq_symbol']} instrument={spec['instrument']} "
         f"filepath={container_source} timezone=Etc/UTC timeframe=H4 "
         "bartype=startofbar errorhandling=stop format=MetaTrader4"),
        (f"-data action=export symbols={spec['sq_symbol']} timeframe=H4 "
         f"datefrom={spec['first']} dateto={spec['last']} outputdir={container_export}"),
    ]


def build(*, market: str, canonical_receipt_path: Path, source_path: Path,
          exported_path: Path, commands_path: Path, output_path: Path,
          sq_version: str = "143.2708") -> dict[str, Any]:
    if market not in MARKETS:
        raise ValueError("unsupported crypto H4 market")
    paths = [path.resolve() for path in (canonical_receipt_path, source_path,
                                         exported_path, commands_path)]
    if any(not path.is_file() for path in paths):
        raise ValueError("SQ H4 resource input missing")
    canonical_path, source, exported, commands = paths
    canonical = _load(canonical_path)
    spec = MARKETS[market]
    if (canonical.get("decision") !=
            "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED"
            or canonical.get("research_symbol") != market
            or canonical.get("source_symbol") != spec["source_symbol"]
            or canonical.get("timeframe") != "H4"
            or canonical.get("timezone") != "UTC"
            or canonical.get("canonical_sha256") != sha256(source)
            or canonical.get("performance_accessed") is not False
            or canonical.get("research_authorized") is not False):
        raise ValueError("canonical receipt does not authorize SQ resource construction")
    observed_commands = commands.read_text().splitlines()
    if observed_commands != expected_commands(market, source, exported.parent):
        raise ValueError("SQ import commands differ from neutral frozen contract")
    roundtrip = audit(source, exported)
    prices = roundtrip["field_errors"]
    exact_ohlc = all(prices[name]["changed_rows"] == 0 for name in
                     ("open", "high", "low", "close"))
    if (roundtrip["source_rows"] != canonical.get("rows")
            or roundtrip["exported_rows"] != canonical.get("rows")
            or roundtrip["timestamps_exact_and_ordered"] is not True
            or not exact_ohlc):
        raise ValueError("SQ H4 round trip is not timestamp/OHLC exact")
    result = {
        "schema_version": 1, "decision": "PASS_SQ_H4_PROXY_RESOURCE",
        "campaign_id": spec["campaign_id"], "symbol": spec["sq_symbol"],
        "timeframe": "H4", "timezone": "Etc/UTC", "sq_version": sq_version,
        "instrument": {"name": spec["instrument"], "data_type": "crypto",
                       "point_value": 1, "tick_size": .01, "tick_step": .01,
                       "default_spread": 0, "order_size_multiplier": 1,
                       "order_size_step": spec["order_size_step"],
                       "role": "gross signal research only"},
        "canonical_receipt": {"path": str(canonical_path),
                              "sha256": sha256(canonical_path)},
        "source": {"path": str(source), "sha256": sha256(source),
                   "rows": canonical["rows"], "first": canonical["first_bar_utc"],
                   "last": canonical["last_bar_utc"]},
        "commands": {"path": str(commands), "sha256": sha256(commands)},
        "roundtrip": {"export_path": str(exported),
                      "export_sha256": sha256(exported),
                      "rows": roundtrip["exported_rows"],
                      "timestamps_exact_and_ordered": True,
                      "exact_ohlc_parity": True,
                      "volume_changed_rows": prices["volume"]["changed_rows"],
                      "volume_max_absolute_error": prices["volume"]["max_absolute_error"]},
        "checks": {"source_hash_exact": True, "row_count_exact": True,
                   "timestamp_roundtrip_exact": True, "ohlc_roundtrip_exact": True,
                   "broker_economics_not_embedded": True,
                   "volume_dependent_rules_forbidden": True},
        "selection_basis": "data_roundtrip_only_no_strategy_performance",
        "performance_accessed": False, "holdout_accessed": False,
        "research_authorized": False,
        "limitations": [
            "Proxy mapping and Ostium cost gates remain mandatory before research.",
            "Volume-dependent rules are forbidden because SQ may normalize volume.",
            "This resource never authorizes paper or live trading."
        ],
        "paper_authorized": False, "live_authorized": False,
    }
    write_json_atomic(output_path.resolve(), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True, choices=tuple(MARKETS))
    parser.add_argument("--canonical-receipt", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--exported", required=True, type=Path)
    parser.add_argument("--commands", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(market=args.market, canonical_receipt_path=args.canonical_receipt,
                   source_path=args.source, exported_path=args.exported,
                   commands_path=args.commands, output_path=args.output)
    print(json.dumps({key: result[key] for key in
                      ("decision", "campaign_id", "symbol", "roundtrip")}, indent=2))


if __name__ == "__main__":
    main()
