#!/usr/bin/env python3
"""Verify the exact US500 D1 SQ import/export resource receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lab.sq_bridge.sq_data_roundtrip_audit import audit


ROOT = Path(__file__).parents[2]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(value: object) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (ROOT / path).resolve()


def verify(receipt_path: Path) -> dict:
    receipt_path = receipt_path.resolve()
    receipt = json.loads(receipt_path.read_text())
    source = _resolve((receipt.get("source") or {}).get("path"))
    commands = _resolve((receipt.get("commands") or {}).get("path"))
    roundtrip = receipt.get("roundtrip") or {}
    exported = _resolve(roundtrip.get("export_path"))
    stored_audit = _resolve(roundtrip.get("audit_path"))
    reasons = []
    if (receipt.get("schema_version") != 1
            or receipt.get("decision") != "PASS_SQ_D1_RESOURCE"
            or receipt.get("symbol") != "US500_ALQ_RTH_D1"
            or receipt.get("timeframe") != "D1"
            or receipt.get("timezone") != "Etc/UTC"
            or receipt.get("performance_accessed") is not False
            or receipt.get("paper_authorized") is not False
            or receipt.get("live_authorized") is not False):
        reasons.append("RESOURCE_IDENTITY_INVALID")
    instrument = receipt.get("instrument") or {}
    if (instrument.get("name") != "US500_ALQ"
            or instrument.get("tick_size") != .001
            or instrument.get("tick_step") != .001
            or instrument.get("default_spread") != 0
            or instrument.get("point_value") != 1):
        reasons.append("NEUTRAL_INSTRUMENT_INVALID")
    for path, digest, label in (
            (source, (receipt.get("source") or {}).get("sha256"), "SOURCE"),
            (commands, (receipt.get("commands") or {}).get("sha256"), "COMMANDS"),
            (exported, roundtrip.get("export_sha256"), "EXPORT"),
            (stored_audit, roundtrip.get("audit_sha256"), "AUDIT")):
        if not path.is_file() or _sha(path) != digest:
            reasons.append(f"{label}_HASH_MISMATCH")
    replay = None
    if not reasons:
        replay = audit(source, exported)
        expected_rows = (receipt.get("source") or {}).get("rows")
        if (not isinstance(expected_rows, int) or isinstance(expected_rows, bool)
                or expected_rows < 1
                or roundtrip.get("rows") != expected_rows
                or replay.get("source_rows") != expected_rows
                or replay.get("exported_rows") != expected_rows
                or replay.get("timestamps_exact_and_ordered") is not True
                or replay.get("exact_numeric_parity") is not True
                or any(row.get("changed_rows") != 0
                       for row in replay.get("field_errors", {}).values())):
            reasons.append("ROUNDTRIP_REPLAY_MISMATCH")
    return {
        "valid": not reasons, "errors": reasons,
        "receipt_path": str(receipt_path), "receipt_sha256": _sha(receipt_path),
        "source_sha256": _sha(source) if source.is_file() else None,
        "export_sha256": _sha(exported) if exported.is_file() else None,
        "replayed_exact_numeric_parity": (
            replay.get("exact_numeric_parity") if replay else False),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
