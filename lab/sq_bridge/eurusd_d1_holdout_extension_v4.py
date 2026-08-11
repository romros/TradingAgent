#!/usr/bin/env python3
"""Extend the canonical EURUSD NY-17 D1 source from a frozen Dukascopy cache."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


MINIMUM_MINUTES = 1368
MAXIMUM_OVERLAP_DELTA_BPS = 5.0
NY = ZoneInfo("America/New_York")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _base(path: Path) -> dict[str, tuple[float, float, float, float, int]]:
    rows = {}
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 7:
                continue
            day = datetime.strptime(row[0], "%Y.%m.%d").date().isoformat()
            values = tuple(float(row[index]) for index in range(2, 6))
            volume = int(float(row[6]))
            if day in rows or not (values[2] <= min(values[0], values[3])
                                   <= max(values[0], values[3]) <= values[1]):
                raise ValueError("invalid canonical base row")
            rows[day] = (*values, volume)
    if len(rows) < 5000 or list(rows) != sorted(rows):
        raise ValueError("canonical base is incomplete or unsorted")
    return rows


def _extension(path: Path) -> dict[str, tuple[float, float, float, float, int, int]]:
    with gzip.open(path, "rt") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("Dukascopy cache must be a JSON array")
    minutes: dict[str, dict[int, list]] = defaultdict(dict)
    for row in raw:
        if not isinstance(row, list) or len(row) < 5:
            raise ValueError("invalid Dukascopy candle")
        stamp = int(row[0])
        local = datetime.fromtimestamp(stamp, timezone.utc).astimezone(NY)
        session = local.date() + (timedelta(days=1) if local.time() >= time(17) else timedelta())
        if session.weekday() < 5:
            minutes[session.isoformat()][stamp] = row
    result = {}
    for day, by_stamp in minutes.items():
        values = [by_stamp[key] for key in sorted(by_stamp)]
        if len(values) < MINIMUM_MINUTES:
            continue
        ohlc = (float(values[0][1]), max(float(row[2]) for row in values),
                min(float(row[3]) for row in values), float(values[-1][4]))
        if not (ohlc[2] <= min(ohlc[0], ohlc[3]) <= max(ohlc[0], ohlc[3]) <= ohlc[1]):
            raise ValueError("invalid aggregated extension OHLC")
        volume = int(round(sum(float(row[5]) for row in values if len(row) > 5)))
        result[day] = (*ohlc, volume, len(values))
    return result


def build(*, base_path: Path, mapping_artifact_path: Path,
          output_path: Path, receipt_path: Path, required_through: str) -> dict:
    base_path, mapping_artifact_path = base_path.resolve(), mapping_artifact_path.resolve()
    mapping = _load(mapping_artifact_path)
    cache = (mapping.get("cache_receipts") or {}).get("mapping_dukascopy") or {}
    cache_path = Path(str(cache.get("path", ""))).resolve()
    if (mapping.get("decision") != "PASS_D1_SOURCE_MAPPING"
            or mapping.get("performance_accessed") is not False
            or not cache_path.is_file() or _sha(cache_path) != cache.get("sha256")):
        raise ValueError("frozen Dukascopy mapping evidence invalid")
    base, extension = _base(base_path), _extension(cache_path)
    overlap = sorted(set(base) & set(extension))
    if not overlap:
        raise ValueError("extension has no overlap with canonical base")
    maximum_delta = max(max(abs(base[day][index] - extension[day][index])
                            for index in range(4)) for day in overlap)
    maximum_delta_bps = max(
        max(abs(base[day][index] - extension[day][index])
            / base[day][index] * 10_000 for index in range(4)) for day in overlap)
    if maximum_delta_bps > MAXIMUM_OVERLAP_DELTA_BPS:
        raise ValueError("extension does not match canonical overlap")
    merged = dict(base)
    # The recent API cache is independently proven against Ostium. Version 2
    # deliberately adopts it for the complete overlap as well as new days;
    # the immutable version-1 source remains untouched.
    merged.update({day: values[:5] for day, values in extension.items()
                   if day <= required_through})
    ordered = sorted(merged)
    if ordered[-1] < required_through:
        raise ValueError("extension does not cover the required holdout end")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=output_path.parent,
                                         prefix=f".{output_path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            for day in ordered:
                open_, high, low, close, volume = merged[day]
                handle.write(f"{day.replace('-', '.')},00:00,{open_:.5f},{high:.5f},"
                             f"{low:.5f},{close:.5f},{volume}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    result = {
        "schema_version": 1, "decision": "PASS_HOLDOUT_SOURCE_EXTENSION",
        "symbol": "EURUSD", "timeframe": "D1", "performance_accessed": False,
        "session_timezone": "America/New_York", "session_boundary": "17:00",
        "minimum_complete_minutes": MINIMUM_MINUTES,
        "base_path": str(base_path), "base_sha256": _sha(base_path),
        "mapping_artifact_path": str(mapping_artifact_path),
        "mapping_artifact_sha256": _sha(mapping_artifact_path),
        "dukascopy_cache_path": str(cache_path), "dukascopy_cache_sha256": _sha(cache_path),
        "overlap_policy": "replace_with_current_dukascopy_api_mapped_to_ostium",
        "maximum_allowed_overlap_delta_bps": MAXIMUM_OVERLAP_DELTA_BPS,
        "overlap_sessions": len(overlap), "maximum_overlap_ohlc_delta": maximum_delta,
        "maximum_overlap_ohlc_delta_bps": maximum_delta_bps,
        "base_rows": len(base), "extension_complete_sessions": len(extension),
        "output_rows": len(ordered), "first": ordered[0], "last": ordered[-1],
        "source_cutoff_policy": "exclude_every_session_after_frozen_holdout_end",
        "required_through": required_through, "output_path": str(output_path),
        "output_sha256": _sha(output_path), "paper_authorized": False,
        "live_authorized": False,
    }
    write_atomic(receipt_path.resolve(), result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--mapping-artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--required-through", default="2026-07-31")
    args = parser.parse_args()
    print(json.dumps(build(base_path=args.base,
                           mapping_artifact_path=args.mapping_artifact,
                           output_path=args.output, receipt_path=args.receipt,
                           required_through=args.required_through), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
