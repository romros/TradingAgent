#!/usr/bin/env python3
"""Audit Dukascopy US-equity M1 and build DST-aware NYSE regular-session D1."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(source_root: Path, symbol: str, output_csv: Path) -> dict[str, object]:
    manifests = sorted((source_root / symbol / "tf=1m").glob("year=*/month=*/manifest.json"))
    if not manifests:
        raise ValueError("no complete monthly manifests")

    by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    source_rows = 0
    duplicate_ts = 0
    seen_ts: set[int] = set()
    source_hashes = []
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        data_path = manifest_path.with_name("data.csv.gz")
        if manifest.get("status") != "complete" or sha256(data_path) != manifest.get("sha256"):
            raise ValueError(f"invalid monthly manifest: {manifest_path}")
        source_hashes.append({"path": str(data_path), "sha256": manifest["sha256"]})
        with gzip.open(data_path, "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                source_rows += 1
                ts = int(row["ts"])
                if ts in seen_ts:
                    duplicate_ts += 1
                seen_ts.add(ts)
                local = datetime.fromtimestamp(ts, timezone.utc).astimezone(NY)
                if time(9, 30) <= local.time() < time(16, 0):
                    by_session[local.date().isoformat()].append(row)

    bad_session_minutes = {day: len(rows) for day, rows in by_session.items()
                           if len(rows) != 390}
    d1_rows = []
    for day, rows in sorted(by_session.items()):
        rows.sort(key=lambda row: int(row["ts"]))
        opens = [float(row["open"]) for row in rows]
        highs = [float(row["high"]) for row in rows]
        lows = [float(row["low"]) for row in rows]
        closes = [float(row["close"]) for row in rows]
        volumes = [float(row["volume"]) for row in rows]
        d1_rows.append({
            "date": day,
            "open": opens[0],
            "high": max(highs),
            "low": min(lows),
            "close": closes[-1],
            "volume": sum(volumes),
            "minutes": len(rows),
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_csv.with_suffix(".tmp.csv")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("date", "open", "high", "low", "close", "volume", "minutes"))
        writer.writeheader()
        writer.writerows(d1_rows)
    temporary.replace(output_csv)

    mechanical_pass = duplicate_ts == 0 and not bad_session_minutes and bool(d1_rows)
    return {
        "schema_version": 1,
        "stage": "US_EQUITY_DATA_PREFLIGHT",
        "symbol": symbol,
        "decision": "PASS_YEAR_PILOT_SOURCE_ONLY" if mechanical_pass else "BLOCK_MECHANICAL_DATA",
        "performance_accessed": False,
        "source_rows": source_rows,
        "unique_timestamps": len(seen_ts),
        "duplicate_timestamps": duplicate_ts,
        "complete_months": len(manifests),
        "rth_timezone": "America/New_York",
        "rth_window": "09:30:00<=local_time<16:00:00",
        "expected_minutes_per_full_session": 390,
        "sessions": len(d1_rows),
        "bad_session_minutes": bad_session_minutes,
        "first_session": d1_rows[0]["date"] if d1_rows else None,
        "last_session": d1_rows[-1]["date"] if d1_rows else None,
        "d1_csv": str(output_csv),
        "d1_sha256": sha256(output_csv),
        "monthly_sources": source_hashes,
        "remaining_blocks": [
            "download_and audit 2018-2025",
            "prove split/dividend adjustment semantics",
            "freeze train/validation/OOS before performance",
            "import and round-trip D1 through SQ"
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source_root, args.symbol.upper(), args.output_csv)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["decision"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
