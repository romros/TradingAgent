#!/usr/bin/env python3
"""Pont nou SQ→Dukascopy→Ostium per certificar EURUSD D1 sense rendiment."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


API_LIMIT = 5000
OHLC_TOLERANCE = 1e-5


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q
    low, high = math.floor(rank), math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - left_mean) ** 2 for a in left)
                            * sum((b - right_mean) ** 2 for b in right))
    return numerator / denominator if denominator else None


def fetch_candles(base_url: str, source: str, from_ts: int, to_ts: int) -> list[list]:
    """Fetch all pages from either DuckDB cursor or legacy offset routes."""
    candles, cursor, offset = [], None, 0
    seen_pages: set[tuple[int | None, int]] = set()
    while True:
        query = {"source": source, "tf": "1m", "from_ts": from_ts,
                 "to_ts": to_ts, "limit": API_LIMIT}
        if cursor is not None:
            query["next_ts"] = cursor
        elif offset:
            query["offset"] = offset
        page_key = (cursor, offset)
        if page_key in seen_pages:
            raise ValueError("Paginacio OHLCV encallada")
        seen_pages.add(page_key)
        url = (base_url.rstrip("/") + "/data/ohlcv/EURUSD?"
               + urllib.parse.urlencode(query))
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
        page = payload.get("candles")
        if not isinstance(page, list):
            raise ValueError("Resposta OHLCV invalida")
        candles.extend(page)
        if not page:
            break
        next_cursor = payload.get("next_ts")
        next_offset = payload.get("next_offset")
        if next_cursor is not None:
            cursor, offset = int(next_cursor), 0
        elif next_offset is not None:
            cursor, offset = None, int(next_offset)
        else:
            break
    unique = {int(row[0]): row for row in candles if isinstance(row, list) and len(row) >= 5}
    return [unique[key] for key in sorted(unique) if from_ts <= key < to_ts]


def read_sq_csv(path: Path, from_ts: int, to_ts: int) -> list[list]:
    rows = []
    fixed_offset = timezone(timedelta(hours=-5))
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 6:
                continue
            try:
                local = datetime.strptime(row[0] + " " + row[1], "%Y.%m.%d %H:%M")
                stamp = int(local.replace(tzinfo=fixed_offset).timestamp())
                if from_ts <= stamp < to_ts:
                    rows.append([stamp, *(float(row[index]) for index in range(2, 6))])
            except ValueError:
                continue
    unique = {int(row[0]): row for row in rows}
    return [unique[key] for key in sorted(unique)]


def compare_sq_dukascopy(sq: list[list], duka: list[list]) -> dict:
    sq_by_ts, duka_by_ts = ({int(row[0]): row for row in values} for values in (sq, duka))
    common = sorted(set(sq_by_ts) & set(duka_by_ts))
    matched = 0
    maximum_delta = 0.0
    for stamp in common:
        delta = max(abs(float(sq_by_ts[stamp][index]) - float(duka_by_ts[stamp][index]))
                    for index in range(1, 5))
        maximum_delta = max(maximum_delta, delta)
        matched += delta <= OHLC_TOLERANCE
    return {
        "sq_rows": len(sq_by_ts), "dukascopy_rows": len(duka_by_ts),
        "common_rows": len(common),
        "sq_coverage_ratio": len(common) / len(sq_by_ts) if sq_by_ts else 0,
        "ohlc_match_ratio": matched / len(common) if common else 0,
        "maximum_ohlc_delta": maximum_delta,
    }


def aggregate_d1(rows: list[list], minimum_minutes: int = 900) -> dict[str, dict]:
    grouped: dict[str, list[list]] = defaultdict(list)
    for row in rows:
        stamp = datetime.fromtimestamp(int(row[0]), timezone.utc)
        grouped[stamp.date().isoformat()].append(row)
    result = {}
    for day, values in grouped.items():
        values.sort(key=lambda row: int(row[0]))
        if len(values) >= minimum_minutes:
            result[day] = {"minutes": len(values), "open": float(values[0][1]),
                           "high": max(float(row[2]) for row in values),
                           "low": min(float(row[3]) for row in values),
                           "close": float(values[-1][4])}
    return result


def compare_mapping(duka_rows: list[list], ostium_rows: list[list]) -> dict:
    duka, ostium = aggregate_d1(duka_rows), aggregate_d1(ostium_rows)
    common = sorted(set(duka) & set(ostium))
    coverage = len(common) / max(len(duka), len(ostium)) if duka or ostium else 0
    close_differences = [abs(duka[day]["close"] - ostium[day]["close"])
                         / ((duka[day]["close"] + ostium[day]["close"]) / 2) * 10_000
                         for day in common]
    duka_returns, ostium_returns = [], []
    for previous, current in zip(common, common[1:]):
        duka_returns.append(duka[current]["close"] / duka[previous]["close"] - 1)
        ostium_returns.append(ostium[current]["close"] / ostium[previous]["close"] - 1)
    return {
        "dukascopy_complete_days": len(duka), "ostium_complete_days": len(ostium),
        "common_complete_days": len(common), "common_day_coverage_ratio": coverage,
        "d1_close_return_correlation": correlation(duka_returns, ostium_returns),
        "d1_return_direction_agreement_ratio": (
            sum((a > 0) == (b > 0) for a, b in zip(duka_returns, ostium_returns))
            / len(duka_returns) if duka_returns else 0),
        "d1_close_difference_p95_bps": percentile(close_differences, .95),
    }


def evaluate(*, sq_rows: list[list], sq_duka_rows: list[list],
             mapping_duka_rows: list[list], mapping_ostium_rows: list[list]) -> dict:
    bridge, mapping = compare_sq_dukascopy(sq_rows, sq_duka_rows), compare_mapping(
        mapping_duka_rows, mapping_ostium_rows)
    checks = {
        "sq_rows": bridge["sq_rows"] >= 5000,
        "sq_coverage": bridge["sq_coverage_ratio"] >= .99,
        "sq_ohlc_match": bridge["ohlc_match_ratio"] >= .99,
        "mapping_days": mapping["common_complete_days"] >= 60,
        "mapping_coverage": mapping["common_day_coverage_ratio"] >= .9,
        "return_correlation": mapping["d1_close_return_correlation"] is not None
            and mapping["d1_close_return_correlation"] >= .99,
        "direction_agreement": mapping["d1_return_direction_agreement_ratio"] >= .95,
        "close_difference": mapping["d1_close_difference_p95_bps"] is not None
            and mapping["d1_close_difference_p95_bps"] <= 5,
    }
    return {"sq_dukascopy_bridge": bridge, "dukascopy_ostium_mapping": mapping,
            "checks": checks, "decision": "PASS_D1_SOURCE_MAPPING" if all(checks.values())
            else "BLOCK_D1_SOURCE_MAPPING"}


def dump_cache(path: Path, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rows, separators=(",", ":")).encode()
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
            handle.write(payload)


def parse_utc(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.astimezone(timezone.utc).timestamp())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8081")
    parser.add_argument("--sq-csv", required=True, type=Path)
    parser.add_argument("--sq-from", required=True)
    parser.add_argument("--sq-to", required=True)
    parser.add_argument("--mapping-from", required=True)
    parser.add_argument("--mapping-to", required=True)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sq_from, sq_to = parse_utc(args.sq_from), parse_utc(args.sq_to)
    mapping_from, mapping_to = parse_utc(args.mapping_from), parse_utc(args.mapping_to)
    sources = {
        "sq_csv": read_sq_csv(args.sq_csv, sq_from, sq_to),
        "sq_leg_dukascopy": fetch_candles(args.base_url, "dukascopy", sq_from, sq_to),
        "mapping_dukascopy": fetch_candles(
            args.base_url, "dukascopy", mapping_from, mapping_to),
        "mapping_ostium": fetch_candles(args.base_url, "ostium", mapping_from, mapping_to),
    }
    cache_receipts = {}
    for name, rows in sources.items():
        if name == "sq_csv":
            continue
        path = args.cache_dir / f"eurusd_{name}.json.gz"
        dump_cache(path, rows)
        cache_receipts[name] = {"path": str(path.resolve()), "sha256": sha256(path),
                                "rows": len(rows)}
    result = evaluate(sq_rows=sources["sq_csv"],
                      sq_duka_rows=sources["sq_leg_dukascopy"],
                      mapping_duka_rows=sources["mapping_dukascopy"],
                      mapping_ostium_rows=sources["mapping_ostium"])
    result.update({
        "schema_version": 1, "symbol": "EURUSD", "timeframe": "D1",
        "performance_accessed": False,
        "sq_csv": {"path": str(args.sq_csv.resolve()), "sha256": sha256(args.sq_csv)},
        "cache_receipts": cache_receipts,
        "windows": {"sq_bridge": [args.sq_from, args.sq_to],
                    "mapping": [args.mapping_from, args.mapping_to]},
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"]}, indent=2))


if __name__ == "__main__":
    main()
