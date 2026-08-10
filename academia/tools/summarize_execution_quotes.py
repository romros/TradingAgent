#!/usr/bin/env python3
"""Summarize normalized executable quotes without storing a raw market feed."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo


REQUIRED_WINDOWS = {"open", "midday", "close"}
NEW_YORK = ZoneInfo("America/New_York")
TARGET_NOTIONALS = (60.0, 100.0, 200.0, 400.0, 500.0)


def _finite(value: object, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile without values")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(rows: list[dict], *, min_days: int = 3, min_per_window: int = 20,
              min_window_span_minutes: float = 30.0) -> dict:
    if min_days <= 0 or min_per_window <= 0 or min_window_span_minutes < 0:
        raise ValueError("coverage thresholds must be positive (span may be zero)")
    accepted: list[dict] = []
    rejected = Counter()
    for row in rows:
        if row.get("instrument") not in {"US500/USD", "SPX/USD"}:
            rejected["wrong_instrument"] += 1
            continue
        if row.get("is_market_open") is not True:
            rejected["market_closed"] += 1
            continue
        window = row.get("session_window")
        if window not in REQUIRED_WINDOWS:
            rejected["invalid_session_window"] += 1
            continue
        try:
            captured = datetime.fromisoformat(str(row["captured_at"]).replace("Z", "+00:00"))
            mid = _finite(row.get("mid"), "mid")
            bid = _finite(row.get("bid"), "bid")
            ask = _finite(row.get("ask"), "ask")
            open_fee = _finite(row.get("open_fee_bps"), "open_fee_bps")
            close_fee = _finite(row.get("close_fee_bps"), "close_fee_bps")
            rollover = row.get("rollover_rate") or {}
            rollover_long = _finite(rollover.get("long"), "rollover.long")
            rollover_short = _finite(rollover.get("short"), "rollover.short")
            simulated = row.get("simulated_slippage") or {}
            impacts = {}
            for side in ("long", "short"):
                by_notional = {_finite(item.get("ntl"), f"{side}.ntl"):
                               _finite(item.get("slippage"), f"{side}.slippage") * 100
                               for item in simulated.get(side, [])}
                if any(notional not in by_notional for notional in TARGET_NOTIONALS):
                    raise ValueError(f"missing {side} target notional")
                impacts[side] = by_notional
        except (KeyError, ValueError):
            rejected["invalid_quote"] += 1
            continue
        if not 0 < bid <= mid <= ask:
            rejected["invalid_quote"] += 1
            continue
        spread_bps = (ask - bid) / mid * 10_000
        accepted.append({
            "captured": captured,
            "day": captured.astimezone(NEW_YORK).date().isoformat(),
            "window": window,
            "spread_bps": spread_bps,
            "open_fee_bps": open_fee,
            "close_fee_bps": close_fee,
            "rollover_long_pct_per_8h": rollover_long,
            "rollover_short_pct_per_8h": rollover_short,
            "slippage_bps": impacts,
            "roundtrip_proxy_bps": {
                notional: spread_bps + open_fee + close_fee
                + impacts["long"][notional] + impacts["short"][notional]
                for notional in TARGET_NOTIONALS
            },
        })

    window_counts = Counter(row["window"] for row in accepted)
    cell_counts = Counter((row["day"], row["window"]) for row in accepted)
    days = sorted({row["day"] for row in accepted})
    cell_spans = {}
    for day in days:
        for window in REQUIRED_WINDOWS:
            timestamps = [row["captured"] for row in accepted
                          if row["day"] == day and row["window"] == window]
            cell_spans[(day, window)] = ((max(timestamps) - min(timestamps)).total_seconds() / 60
                                         if timestamps else 0.0)
    qualifying_days = [day for day in days if all(
        cell_counts[(day, window)] >= min_per_window
        and cell_spans[(day, window)] >= min_window_span_minutes
        for window in REQUIRED_WINDOWS)]
    coverage_pass = len(qualifying_days) >= min_days
    # Once coverage passes, a later partial day cannot alter frozen estimates.
    # Before that, accepted rows remain explicitly provisional diagnostics.
    statistical_rows = ([row for row in accepted if row["day"] in qualifying_days]
                        if coverage_pass else accepted)
    spreads = [row["spread_bps"] for row in statistical_rows]
    by_window = {}
    for window in sorted(REQUIRED_WINDOWS):
        values = [row["spread_bps"] for row in statistical_rows if row["window"] == window]
        by_window[window] = None if not values else {
            "median": median(values), "p90": percentile(values, 0.90),
            "p95": percentile(values, 0.95), "maximum": max(values)}
    slippage_summary = {}
    roundtrip_summary = {}
    for notional in TARGET_NOTIONALS:
        label = str(int(notional))
        slippage_summary[label] = {}
        for side in ("long", "short"):
            values = [row["slippage_bps"][side][notional] for row in statistical_rows]
            slippage_summary[label][side] = None if not values else {
                "median": median(values), "p95": percentile(values, 0.95), "maximum": max(values)}
        values = [row["roundtrip_proxy_bps"][notional] for row in statistical_rows]
        roundtrip_summary[label] = None if not values else {
            "median": median(values), "p95": percentile(values, 0.95), "maximum": max(values)}
    rollover_summary = {}
    for side in ("long", "short"):
        values = [row[f"rollover_{side}_pct_per_8h"] for row in statistical_rows]
        rollover_summary[side] = None if not values else {
            "median": median(values), "minimum": min(values), "maximum": max(values)}
    return {
        "schema_version": 2,
        "accepted_samples": len(accepted),
        "statistical_samples": len(statistical_rows),
        "statistics_scope": ("qualifying_complete_days_only" if coverage_pass
                             else "all_accepted_provisional"),
        "rejected_samples": dict(sorted(rejected.items())),
        "distinct_open_days": len(days),
        "samples_by_window": {window: window_counts[window] for window in sorted(REQUIRED_WINDOWS)},
        "samples_by_day_and_window": {
            day: {window: cell_counts[(day, window)] for window in sorted(REQUIRED_WINDOWS)}
            for day in days
        },
        "span_minutes_by_day_and_window": {
            day: {window: cell_spans[(day, window)] for window in sorted(REQUIRED_WINDOWS)}
            for day in days
        },
        "qualifying_complete_days": qualifying_days,
        "frozen_coverage_gate": {
            "minimum_distinct_open_days": min_days,
            "minimum_samples_per_window_per_day": min_per_window,
            "minimum_span_minutes_per_window_per_day": min_window_span_minutes,
            "pass": coverage_pass,
        },
        "spread_bps": None if not spreads else {
            "median": median(spreads),
            "p90": percentile(spreads, 0.90),
            "p95": percentile(spreads, 0.95),
            "maximum": max(spreads),
        },
        "spread_bps_by_window": by_window,
        "slippage_bps_by_notional_and_side": slippage_summary,
        "roundtrip_proxy_bps_by_notional": roundtrip_summary,
        "roundtrip_proxy_definition": "full bid-ask spread + open fee + close fee + long entry impact + short entry impact; carry and refundable oracle fee excluded",
        "rollover_pct_per_8h": rollover_summary,
        "decision": "MEASURED" if coverage_pass else "INSUFFICIENT_OPEN_SESSION_COVERAGE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSONL normalized quote samples")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-days", type=int, default=3)
    parser.add_argument("--min-per-window", type=int, default=20)
    parser.add_argument("--min-window-span-minutes", type=float, default=30.0)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    result = summarize(rows, min_days=args.min_days, min_per_window=args.min_per_window,
                       min_window_span_minutes=args.min_window_span_minutes)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
