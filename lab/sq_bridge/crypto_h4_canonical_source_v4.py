#!/usr/bin/env python3
"""Build performance-blind UTC H4 proxy sources from frozen Binance M1 data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator


UTC = timezone.utc
MINUTES_PER_BUCKET = 240


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", dir=path.parent, prefix=f".{path.name}.",
                delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        path.chmod(0o644)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("source manifest must be a JSON object")
    return value


def _parse_row(row: list[str], line: int) -> tuple[datetime, tuple[Decimal, ...]]:
    if len(row) != 7:
        raise ValueError(f"line {line}: expected 7 MT4 columns, found {len(row)}")
    try:
        stamp = datetime.strptime(f"{row[0]} {row[1]}", "%Y.%m.%d %H:%M").replace(
            tzinfo=UTC)
        values = tuple(Decimal(value) for value in row[2:])
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f"line {line}: invalid timestamp or number") from exc
    open_, high, low, close, volume = values
    if (min(open_, high, low, close) <= 0 or volume < 0
            or high < max(open_, low, close) or low > min(open_, high, close)):
        raise ValueError(f"line {line}: invalid OHLCV")
    return stamp, values


def _bucket_start(stamp: datetime) -> datetime:
    return stamp.replace(hour=(stamp.hour // 4) * 4, minute=0)


def aggregate(path: Path) -> tuple[list[tuple], dict[str, Any]]:
    complete: list[tuple] = []
    current_start: datetime | None = None
    bucket: list[tuple[datetime, tuple[Decimal, ...]]] = []
    previous: datetime | None = None
    rows = missing_minutes = gap_intervals = 0
    first: datetime | None = None

    def finish() -> None:
        if not bucket:
            return
        expected = current_start
        exact = (len(bucket) == MINUTES_PER_BUCKET
                 and all(stamp == expected.replace(
                     minute=index % 60,
                     hour=current_start.hour + index // 60)
                         for index, (stamp, _) in enumerate(bucket)))
        if exact:
            values = [item[1] for item in bucket]
            complete.append((current_start, values[0][0],
                             max(value[1] for value in values),
                             min(value[2] for value in values), values[-1][3],
                             sum((value[4] for value in values), Decimal(0))))

    with path.open(newline="") as handle:
        for line, raw in enumerate(csv.reader(handle), 1):
            stamp, values = _parse_row(raw, line)
            if first is None:
                first = stamp
            if previous is not None:
                delta = int((stamp - previous).total_seconds() // 60)
                if delta <= 0:
                    raise ValueError(f"line {line}: timestamps are duplicate or unordered")
                if delta > 1:
                    gap_intervals += 1
                    missing_minutes += delta - 1
            start = _bucket_start(stamp)
            if current_start is not None and start != current_start:
                finish()
                bucket = []
            current_start = start
            bucket.append((stamp, values))
            previous = stamp
            rows += 1
    finish()
    if first is None or previous is None:
        raise ValueError("empty source")
    inventory = {
        "rows": rows, "first_utc": first.isoformat(),
        "last_utc": previous.isoformat(), "gap_intervals": gap_intervals,
        "missing_minutes": missing_minutes,
    }
    return complete, inventory


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def build(*, source_path: Path, manifest_path: Path, output_path: Path,
          receipt_path: Path) -> dict[str, Any]:
    source_path, manifest_path = source_path.resolve(), manifest_path.resolve()
    if not source_path.is_file() or not manifest_path.is_file():
        raise ValueError("crypto source input missing")
    manifest = _load_manifest(manifest_path)
    source_hash = sha256(source_path)
    if (manifest.get("source") != "Binance official public spot monthly klines"
            or manifest.get("timeframe") != "M1"
            or manifest.get("timezone") != "UTC"
            or manifest.get("output_sha256") != source_hash
            or manifest.get("research_authorized") is not False
            or manifest.get("paper_or_live_authorized") is not False
            or manifest.get("symbol") not in {"BTCUSDT", "ETHUSDT"}):
        raise ValueError("manifest does not authorize canonical proxy construction")
    archive_chain = verify_archives(manifest_path)
    if archive_chain["decision"] != "PASS_ARCHIVE_CHAIN":
        raise ValueError("source archive chain differs from frozen manifest")
    bars, inventory = aggregate(source_path)
    continuity = manifest.get("continuity") or {}
    if (inventory["rows"] != manifest.get("rows")
            or inventory["first_utc"] != manifest.get("first_utc")
            or inventory["last_utc"] != manifest.get("last_utc")
            or inventory["gap_intervals"] != continuity.get("gap_intervals")
            or inventory["missing_minutes"] != continuity.get("missing_minutes")):
        raise ValueError("source inventory differs from frozen manifest")
    total_possible = int((datetime.fromisoformat(inventory["last_utc"])
                          - datetime.fromisoformat(inventory["first_utc"])
                          ).total_seconds() // (4 * 3600)) + 1
    if len(bars) < 365 * 6 * 5 or len(bars) / total_possible < .99:
        raise ValueError("insufficient complete H4 coverage")

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", newline="", dir=output_path.parent,
                prefix=f".{output_path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            writer = csv.writer(handle, lineterminator="\n")
            for stamp, *values in bars:
                writer.writerow((stamp.strftime("%Y.%m.%d"),
                                 stamp.strftime("%H:%M"),
                                 *(_decimal(value) for value in values)))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output_path)
        output_path.chmod(0o644)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

    base = manifest["symbol"][:-1]  # BTCUSDT -> BTCUSD; ETHUSDT -> ETHUSD
    receipt = {
        "schema_version": 1,
        "decision": "PASS_CANONICAL_H4_PROXY_SOURCE_NOT_RESEARCH_AUTHORIZED",
        "campaign_id": f"{base.lower()}-h4-alquimia-v4",
        "research_symbol": base, "source_symbol": manifest["symbol"],
        "timeframe": "H4", "timezone": "UTC",
        "bucket_alignment_hours_utc": [0, 4, 8, 12, 16, 20],
        "complete_minutes_required_per_bar": MINUTES_PER_BUCKET,
        "rows": len(bars), "possible_buckets": total_possible,
        "coverage_ratio": len(bars) / total_possible,
        "dropped_incomplete_buckets": total_possible - len(bars),
        "first_bar_utc": bars[0][0].isoformat(),
        "last_bar_utc": bars[-1][0].isoformat(),
        "source_inventory": inventory,
        "source_path": str(source_path), "source_sha256": source_hash,
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256(manifest_path),
        "archive_chain": archive_chain,
        "canonical_path": str(output_path),
        "canonical_sha256": sha256(output_path),
        "selection_basis": "provenance_continuity_and_coverage_only_no_returns",
        "proxy_mapping_required": True, "performance_accessed": False,
        "holdout_accessed": False, "research_authorized": False,
        "paper_authorized": False, "live_authorized": False,
    }
    write_json_atomic(receipt_path.resolve(), receipt)
    return receipt


def verify_archives(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path.resolve())
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest has no source archives")
    mismatches = []
    for row in sources:
        archive = Path(row.get("archive", ""))
        if not archive.is_file() or sha256(archive) != row.get("sha256"):
            mismatches.append(str(archive))
    return {"archives": len(sources), "mismatches": mismatches,
            "decision": "PASS_ARCHIVE_CHAIN" if not mismatches else "FAIL_ARCHIVE_CHAIN"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--verify-archives", action="store_true")
    args = parser.parse_args()
    if args.verify_archives:
        print(json.dumps(verify_archives(args.manifest), indent=2))
        return
    if args.source is None or args.output is None or args.receipt is None:
        parser.error("--source, --output and --receipt are required to build")
    result = build(source_path=args.source, manifest_path=args.manifest,
                   output_path=args.output, receipt_path=args.receipt)
    print(json.dumps({key: result[key] for key in (
        "decision", "rows", "coverage_ratio", "dropped_incomplete_buckets",
        "first_bar_utc", "last_bar_utc")}, indent=2))


if __name__ == "__main__":
    main()
