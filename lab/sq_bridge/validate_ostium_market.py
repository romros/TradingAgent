#!/usr/bin/env python3
"""Gate previ: només permet campanyes amb mapping SQ-BS-Ostium complet."""

import argparse
import json
from pathlib import Path


REQUIRED = ("ostium_pair", "ostium_asset", "bs_symbol", "sq_symbol", "venue_max_leverage")


def validate(registry: Path, market: str) -> dict:
    data = json.loads(registry.read_text(encoding="utf-8"))
    entry = data.get("markets", {}).get(market.upper())
    if not isinstance(entry, dict) or entry.get("research_eligible") is not True:
        raise ValueError(f"{market}: absent o no autoritzat per recerca Ostium")
    missing = [key for key in REQUIRED if entry.get(key) in (None, "")]
    if missing:
        raise ValueError(f"{market}: mapping incomplet: {', '.join(missing)}")
    return {
        "status": "PASS_RESEARCH",
        "market": market.upper(),
        "mapping": entry,
        "live_authorized": entry.get("live_eligible") is True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("market")
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("ostium_markets.json"))
    args = parser.parse_args()
    try:
        result = validate(args.registry, args.market)
    except ValueError as exc:
        print(json.dumps({"status": "REJECT", "reason": str(exc)}, indent=2))
        raise SystemExit(2)
    print(json.dumps(result, indent=2))
