#!/usr/bin/env python3
"""Fail-closed receipt for the canonical EURUSD D1 import into SQ 143."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED = {
    "symbol": "EURUSD_ALQ_NY17_D1",
    "instrument": "EURUSD",
    "timeframe": "D1",
    "timezone": "Etc/UTC",
    "first": "2003-05-05",
    "last": "2026-02-26",
    "rows": 5884,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(source_receipt: dict, catalog_observation: dict,
             commands_path: Path, roundtrip_path: Path | None = None) -> dict:
    output = source_receipt.get("output") or {}
    source_checks = {
        "canonical_source_pass": source_receipt.get("decision") == "PASS_CANONICAL_D1_IMPORT_SOURCE",
        "source_rows": source_receipt.get("rows") == EXPECTED["rows"],
        "source_dates": (source_receipt.get("first"), source_receipt.get("last"))
                        == (EXPECTED["first"], EXPECTED["last"]),
        "source_has_no_weekends": source_receipt.get("weekend_rows") == 0,
        "source_csv_hash_present": bool(output.get("sha256")),
    }
    catalog_checks = {
        key: catalog_observation.get(key) == expected
        for key, expected in EXPECTED.items()
    }
    roundtrip_available = roundtrip_path is not None and roundtrip_path.is_file()
    checks = {**source_checks, **{f"catalog_{key}": value
                                  for key, value in catalog_checks.items()},
              "full_sq_ohlc_roundtrip_available": roundtrip_available}
    # Presence is not parity. The existing resource auditor must compare a full
    # SQ export before this receipt can ever authorize research.
    reasons = []
    if not all(source_checks.values()):
        reasons.append("CANONICAL_SOURCE_INVALID")
    if not all(catalog_checks.values()):
        reasons.append("SQ_CATALOG_OBSERVATION_MISMATCH")
    if not roundtrip_available:
        reasons.append("SQ_D1_ROUNDTRIP_UNAVAILABLE")
    return {
        "schema_version": 1,
        "symbol": EXPECTED["symbol"],
        "timeframe": "D1",
        "session_timezone": "America/New_York",
        "session_boundary": "17:00",
        "sq_version": "143.2708",
        "performance_accessed": False,
        "source_receipt": source_receipt,
        "catalog_observation": catalog_observation,
        "import_commands": {"path": str(commands_path),
                            "sha256": sha256(commands_path)},
        "roundtrip_export": str(roundtrip_path) if roundtrip_available else None,
        "checks": checks,
        "blocking_reasons": reasons,
        "decision": "BLOCK_SQ_D1_ROUNDTRIP_UNAVAILABLE" if reasons
                    else "READY_FOR_SQ_D1_RESOURCE_AUDIT",
        "research_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--catalog-observation", type=Path, required=True)
    parser.add_argument("--commands", type=Path, required=True)
    parser.add_argument("--roundtrip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.source_receipt.read_text()),
                      json.loads(args.catalog_observation.read_text()),
                      args.commands, args.roundtrip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "blocking_reasons": result["blocking_reasons"]}, indent=2))


if __name__ == "__main__":
    main()
