#!/usr/bin/env python3
"""Maturity gate for a native Ostium M1 recorder before proxy parity."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def inventory(root: Path, now_ts: int, minimum_days: int = 60,
              minimum_coverage_ratio: float = .90, maximum_stale_seconds: int = 180) -> dict:
    files = sorted(path for path in root.glob("*/*.csv") if path.is_file())
    rows: dict[int, tuple[float, float, float, float]] = {}
    duplicates = invalid = 0
    hashes = {}
    for path in files:
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(newline="") as handle:
            for raw in csv.reader(handle):
                if not raw:
                    continue
                try:
                    ts = int(raw[0]); values = tuple(float(value) for value in raw[1:5])
                except (ValueError, IndexError):
                    invalid += 1; continue
                opened, high, low, close = values
                if min(values) <= 0 or high < max(opened, close) or low > min(opened, close) or ts % 60:
                    invalid += 1; continue
                if ts in rows:
                    duplicates += 1
                rows[ts] = values
    timestamps = sorted(rows)
    first, last = (timestamps[0], timestamps[-1]) if timestamps else (None, None)
    observed_span_days = (last - first) / 86400 if first is not None else 0
    expected = ((last - first) // 60 + 1) if first is not None else 0
    ratio = len(rows) / expected if expected else 0
    stale = now_ts - last if last is not None else None
    ready_not_before_ts = first + minimum_days * 86400 if first is not None else None
    reasons = []
    if not rows: reasons.append("NO_NATIVE_CANDLES")
    if invalid: reasons.append("INVALID_CANDLES_PRESENT")
    if duplicates: reasons.append("DUPLICATE_TIMESTAMPS_PRESENT")
    if observed_span_days < minimum_days: reasons.append(f"SPAN_LT_{minimum_days}_DAYS")
    if ratio < minimum_coverage_ratio: reasons.append("COVERAGE_RATIO_BELOW_THRESHOLD")
    if stale is None or stale > maximum_stale_seconds: reasons.append("RECORDER_STALE")
    hard = any(reason in reasons for reason in ("INVALID_CANDLES_PRESENT", "DUPLICATE_TIMESTAMPS_PRESENT", "RECORDER_STALE"))
    decision = "BLOCK" if hard else ("READY_FOR_PARITY" if not reasons else "WARMING")
    return {
        "schema_version": 1, "gate_id": "ostium-native-m1-maturity-v1",
        "root": str(root), "files": hashes, "candles": len(rows),
        "first_ts": first, "last_ts": last, "observed_span_days": round(observed_span_days, 6),
        "ready_not_before_utc": datetime.fromtimestamp(ready_not_before_ts, timezone.utc).isoformat() if ready_not_before_ts else None,
        "expected_minutes_in_span": expected, "coverage_ratio": round(ratio, 6),
        "last_candle_age_seconds": stale, "invalid_rows": invalid, "duplicate_timestamps": duplicates,
        "thresholds": {"minimum_days": minimum_days, "minimum_coverage_ratio": minimum_coverage_ratio,
                       "maximum_stale_seconds": maximum_stale_seconds},
        "decision": decision, "reasons": reasons,
        "scope": "RECORDER_MATURITY_ONLY; DOES_NOT_PROVE_SQ_PROXY_PARITY_OR_AUTHORIZE_RESEARCH",
        "research_authorized": False, "paper_or_live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now-ts", type=int, default=None)
    parser.add_argument("--minimum-days", type=int, default=60)
    parser.add_argument("--minimum-coverage-ratio", type=float, default=.90)
    parser.add_argument("--maximum-stale-seconds", type=int, default=180)
    parser.add_argument("--fail-unless-ready", action="store_true")
    args = parser.parse_args()
    result = inventory(args.root, args.now_ts or int(time.time()), args.minimum_days,
                       args.minimum_coverage_ratio, args.maximum_stale_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if args.fail_unless_ready and result["decision"] != "READY_FOR_PARITY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
