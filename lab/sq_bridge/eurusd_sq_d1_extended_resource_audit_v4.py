#!/usr/bin/env python3
"""Audit the versioned holdout-complete EURUSD D1 SQ round-trip."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _rows(path: Path) -> dict[str, tuple[float, float, float, float, int]]:
    result = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) >= 7:
                result[row[0]] = (*(float(row[index]) for index in range(2, 6)),
                                  int(float(row[6])))
    return result


def audit(*, extension_receipt_path: Path, parity_contract_path: Path,
          output_path: Path, symbol: str = "EURUSD_ALQ_NY17_D1_V3") -> dict:
    extension_receipt_path = extension_receipt_path.resolve()
    parity_contract_path = parity_contract_path.resolve()
    extension, parity = _load(extension_receipt_path), _load(parity_contract_path)
    source = Path(str(extension.get("output_path", ""))).resolve()
    exported = Path(str(parity.get("sq_candles_path", ""))).resolve()
    if (extension.get("decision") != "PASS_HOLDOUT_SOURCE_EXTENSION"
            or extension.get("performance_accessed") is not False
            or not source.is_file() or _sha(source) != extension.get("output_sha256")
            or parity.get("decision") != "PASS_CANDLE_PARITY"
            or parity.get("performance_accessed") is not False
            or parity.get("dukascopy_candles_sha256") != _sha(source)
            or not exported.is_file() or parity.get("sq_candles_sha256") != _sha(exported)):
        raise ValueError("extended SQ resource lineage invalid")
    source_rows, sq_rows = _rows(source), _rows(exported)
    common = sorted(set(source_rows) & set(sq_rows))
    price_delta = max((abs(source_rows[day][index] - sq_rows[day][index])
                       for day in common for index in range(4)), default=1.0)
    volume_changes = [{"day": day, "source": source_rows[day][4],
                       "sq_export": sq_rows[day][4]}
                      for day in common if source_rows[day][4] != sq_rows[day][4]]
    checks = {
        "extension_receipt_pass": True,
        "holdout_covered": extension.get("last", "") >= extension.get("required_through", "~"),
        "identical_dates": set(source_rows) == set(sq_rows),
        "expected_row_count": len(source_rows) == len(sq_rows) == parity.get("sq_rows"),
        "exact_ohlc_roundtrip": len(common) == len(source_rows) and price_delta == 0,
        "only_zero_volume_normalized": all(
            row["source"] == 0 and row["sq_export"] == 1 for row in volume_changes),
    }
    result = {
        "schema_version": 1, "decision": "PASS_SQ_D1_RESOURCE" if all(checks.values()) else "BLOCK_SQ_D1_RESOURCE",
        "symbol": symbol, "instrument": "EURUSD", "timeframe": "D1",
        "sq_version": "143.2708", "session_timezone": "America/New_York",
        "session_boundary": "17:00", "checks": checks,
        "source_rows": len(source_rows), "sq_rows": len(sq_rows),
        "common_rows": len(common), "ohlc_match_ratio": (
            len(common) / len(source_rows) if source_rows and price_delta == 0 else 0),
        "maximum_ohlc_delta": price_delta, "sunday_fragment_bars": 0,
        "first": min(common, default=None), "last": max(common, default=None),
        "required_through": extension.get("required_through"),
        "source_csv": {"path": str(source), "bytes": source.stat().st_size,
                       "sha256": _sha(source)},
        "sq_export": {"path": str(exported), "bytes": exported.stat().st_size,
                      "sha256": _sha(exported)},
        "extension_receipt_path": str(extension_receipt_path),
        "extension_receipt_sha256": _sha(extension_receipt_path),
        "parity_contract_path": str(parity_contract_path),
        "parity_contract_sha256": _sha(parity_contract_path),
        "volume_normalizations": volume_changes, "performance_accessed": False,
        "research_authorized": all(checks.values()), "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(output_path.resolve(), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension-receipt", required=True, type=Path)
    parser.add_argument("--parity-contract", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--symbol", default="EURUSD_ALQ_NY17_D1_V3")
    args = parser.parse_args()
    print(json.dumps(audit(extension_receipt_path=args.extension_receipt,
                           parity_contract_path=args.parity_contract,
                           output_path=args.output, symbol=args.symbol),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
