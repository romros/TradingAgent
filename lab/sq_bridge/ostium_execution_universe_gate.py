#!/usr/bin/env python3
"""Merge per-pair execution summaries without promoting one-shot economics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build(summaries: list[dict[str, Any]], expected_symbols: set[str] | None = None) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        instrument = summary.get("instrument") or {}
        symbol = f'{instrument.get("pair_from", "")}/{instrument.get("pair_to", "")}'
        if not instrument.get("pair_id") or symbol == "/":
            raise ValueError("summary is missing normalized instrument identity")
        if symbol in rows:
            raise ValueError(f"duplicate summary for {symbol}")
        samples = int(summary.get("open_market_snapshots", 0))
        gate = (summary.get("gate") or {}).get("execution_economics")
        if gate not in {"PASS", "INSUFFICIENT_OPEN_MARKET_EVIDENCE"}:
            raise ValueError(f"unknown execution gate for {symbol}: {gate}")
        observed = samples > 0
        rows[symbol] = {
            "pair_id": str(instrument["pair_id"]),
            "category": instrument.get("category"),
            "open_samples": samples,
            "first_open_capture_at": summary.get("first_open_capture_at"),
            "last_open_capture_at": summary.get("last_open_capture_at"),
            "source_raw_sha256": summary.get("source_raw_sha256", []),
            "distinct_utc_days": summary["gate"]["checks"]["distinct_utc_days"]["actual"],
            "distinct_utc_hours": summary["gate"]["checks"]["distinct_utc_hours"]["actual"],
            "execution_economics_gate": gate,
            "research_cost_observation": "OBSERVED_PROVISIONAL" if observed and gate != "PASS" else (
                "OBSERVED_GATE_PASS" if gate == "PASS" else "MISSING"),
            "multiday_research": "COST_MODEL_READY" if gate == "PASS" else "BLOCKED_ROLLOVER_SERIES",
            "paper": "REQUIRES_STRATEGY_GATES" if gate == "PASS" else "BLOCKED_EXECUTION_ECONOMICS",
            "spread_p50_bps": summary.get("spread_bps", {}).get("p50"),
            "spread_p95_bps": summary.get("spread_bps", {}).get("p95"),
            "open_fee_bps_p50": summary.get("fees", {}).get("open_fee_bps", {}).get("p50"),
            "rollover_long_pct_per_8h_p50": summary.get("fees", {}).get(
                "rollover_long_pct_per_8h", {}).get("p50"),
            "rollover_short_pct_per_8h_p50": summary.get("fees", {}).get(
                "rollover_short_pct_per_8h", {}).get("p50"),
            "venue_max_leverage_p50": summary.get("limits", {}).get("max_leverage", {}).get("p50"),
            "min_notional_usd_p50": summary.get("limits", {}).get("min_notional_usd", {}).get("p50"),
        }
    missing = sorted((expected_symbols or set()) - set(rows))
    unexpected = sorted(set(rows) - (expected_symbols or set(rows)))
    all_expected_present = not missing and not unexpected
    ready = sorted(symbol for symbol, row in rows.items()
                   if row["execution_economics_gate"] == "PASS")
    return {
        "schema_version": 1,
        "expected_symbols": sorted(expected_symbols or rows),
        "all_expected_present": all_expected_present,
        "missing_symbols": missing,
        "unexpected_symbols": unexpected,
        "markets": dict(sorted(rows.items())),
        "execution_ready_symbols": ready,
        "decision": "PASS_ALL_EXECUTION_GATES" if all_expected_present and len(ready) == len(rows) else
                    "COLLECT_MORE_OPEN_MARKET_EVIDENCE",
        "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--expected", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = build([json.loads(path.read_text()) for path in args.paths], set(args.expected) or None)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
