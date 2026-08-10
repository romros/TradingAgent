#!/usr/bin/env python3
"""Summarize read-only XAU/USD execution economics around one FOMC statement."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
EXPECTED_PAIR_ID = "5"
EXPECTED_PAIR = ("XAU", "USD")
PHASE_REQUIREMENTS = {"pre": 10, "reaction": 20, "post": 60}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def phase_for(stamp: datetime) -> str | None:
    local = stamp.astimezone(NY)
    value = local.time().replace(tzinfo=None)
    if time(13, 45) <= value < time(14, 0):
        return "pre"
    if time(14, 0) <= value <= time(14, 30, 59, 999999):
        return "reaction"
    if time(14, 31) <= value <= time(16, 45, 59, 999999):
        return "post"
    return None


def _stamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("captured_at must include a timezone")
    return parsed


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {"n": len(values), "p50": percentile(values, .5),
            "p95": percentile(values, .95), "max": max(values) if values else None}


def _slippage(row: dict[str, Any], side: str, notional: float) -> float:
    matches = [float(point["slippage_bps"])
               for point in row.get("simulated_slippage", {}).get(side, [])
               if float(point["notional_usd"]) == notional]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {side} slippage point for notional {notional:g}")
    return matches[0]


def evaluate(snapshots: list[dict[str, Any]], *, event_date: date,
             notionals: tuple[float, ...] = (200, 400, 500, 600),
             source_paths: list[Path] | None = None) -> dict[str, Any]:
    if not snapshots:
        raise ValueError("at least one snapshot is required")
    observations: dict[str, list[dict[str, Any]]] = {phase: [] for phase in PHASE_REQUIREMENTS}
    seen_minutes: set[str] = set()
    outside_window = 0
    closed_market = 0

    for row in snapshots:
        instrument = row.get("instrument", {})
        identity = (str(instrument.get("pair_id")),
                    str(instrument.get("pair_from", "")).upper(),
                    str(instrument.get("pair_to", "")).upper())
        if identity != (EXPECTED_PAIR_ID, *EXPECTED_PAIR):
            raise ValueError(f"snapshot identity is {identity}, expected ('5', 'XAU', 'USD')")
        stamp = _stamp(str(row.get("captured_at")))
        local = stamp.astimezone(NY)
        if local.date() != event_date:
            raise ValueError(f"snapshot date {local.date()} does not match event date {event_date}")
        phase = phase_for(stamp)
        if phase is None:
            outside_window += 1
            continue
        minute = local.strftime("%Y-%m-%dT%H:%M")
        if minute in seen_minutes:
            raise ValueError(f"duplicate local capture minute: {minute}")
        seen_minutes.add(minute)
        if row.get("market_state", {}).get("is_market_open") is not True:
            closed_market += 1
            continue
        observations[phase].append(row)

    phases: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    for phase, required in PHASE_REQUIREMENTS.items():
        rows = observations[phase]
        checks[phase] = {"actual_open_distinct_minutes": len(rows),
                         "required_open_distinct_minutes": required,
                         "pass": len(rows) >= required}
        by_notional = {}
        for notional in notionals:
            costs = []
            long_routes = []
            short_routes = []
            for row in rows:
                fees = float(row["fees"]["open_fee_bps"]) + float(row["fees"]["close_fee_bps"])
                spread = float(row["quote"]["spread_bps"])
                long_slip = _slippage(row, "long", notional)
                short_slip = _slippage(row, "short", notional)
                costs.append(fees + spread + long_slip + short_slip)
                long_routes.append(fees + spread + 2 * long_slip)
                short_routes.append(fees + spread + 2 * short_slip)
            by_notional[format(notional, "g")] = {
                "direction_neutral_roundtrip_proxy_bps": _distribution(costs),
                "long_roundtrip_proxy_bps": _distribution(long_routes),
                "short_roundtrip_proxy_bps": _distribution(short_routes),
            }
        phases[phase] = {
            "open_distinct_minutes": len(rows),
            "spread_bps": _distribution([float(row["quote"]["spread_bps"]) for row in rows]),
            "estimated_cost_by_notional": by_notional,
        }

    ready = all(check["pass"] for check in checks.values())
    raw_hashes = sorted({str(row.get("source", {}).get("raw_sha256")) for row in snapshots
                         if row.get("source", {}).get("raw_sha256")})
    path_hashes = []
    for path in source_paths or []:
        path_hashes.append({"path": str(path),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "schema_version": 1,
        "experiment": "XAUUSD_FOMC_EVENT_EXECUTION_ECONOMICS",
        "event_date": event_date.isoformat(),
        "event_timezone": "America/New_York",
        "assumed_statement_time": "14:00",
        "instrument": {"pair_id": EXPECTED_PAIR_ID, "pair_from": "XAU", "pair_to": "USD"},
        "phase_windows": {"pre": "13:45:00-13:59:59", "reaction": "14:00:00-14:30:59",
                          "post": "14:31:00-16:45:59"},
        "input_snapshots": len(snapshots),
        "outside_window_snapshots": outside_window,
        "closed_market_snapshots_in_window": closed_market,
        "raw_source_sha256": raw_hashes,
        "normalized_source_files": path_hashes,
        "phases": phases,
        "gate": {
            "checks": checks,
            "status": "EVENT_EXECUTION_EVIDENCE_READY" if ready else "INSUFFICIENT_EVENT_EXECUTION_EVIDENCE",
            "meaning": "Permet dissenyar una campanya nova; no reobre v29 ni autoritza paper o live.",
        },
        "cost_model": {
            "unit": "basis_points_of_notional",
            "direction_neutral_formula": "open_fee + close_fee + spread + long_simulated_slippage + short_simulated_slippage",
            "route_formula": "open_fee + close_fee + spread + 2 * same_side_simulated_slippage",
            "limitation": "SDK quote and simulated-slippage proxy, not observed fills.",
        },
        "read_only": True,
        "performance_accessed": False,
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--event-date", type=date.fromisoformat, required=True)
    parser.add_argument("--notionals", default="200,400,500,600")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    notionals = tuple(float(value) for value in args.notionals.split(","))
    result = evaluate([json.loads(path.read_text()) for path in args.paths],
                      event_date=args.event_date, notionals=notionals, source_paths=args.paths)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
