#!/usr/bin/env python3
"""Freeze US500 small-account cost scenarios from a measured session summary."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

TARGET_NOTIONALS_USDC = (60, 100, 200, 400, 500)
MINIMUM_DAYS = 3
MINIMUM_SAMPLES_PER_WINDOW = 20
MINIMUM_WINDOW_SPAN_MINUTES = 30.0


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _finite_nonnegative(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def derive(summary: dict[str, Any], *, oracle_locked_usdc: float = 0.10) -> dict[str, Any]:
    oracle_locked_usdc = _finite_nonnegative(oracle_locked_usdc, "oracle_locked_usdc")
    measured = summary.get("decision") == "MEASURED"
    coverage = summary.get("frozen_coverage_gate") or {}
    if not measured or coverage.get("pass") is not True:
        return {"schema_version": 1, "decision": "BLOCK_INSUFFICIENT_EXECUTION_COVERAGE",
                "costs_frozen": False, "source_decision": summary.get("decision"),
                "qualifying_complete_days": summary.get("qualifying_complete_days", [])}
    if summary.get("schema_version") != 2:
        raise ValueError("measured summary must use execution-summary schema version 2")
    contract = {
        "minimum_distinct_open_days": MINIMUM_DAYS,
        "minimum_samples_per_window_per_day": MINIMUM_SAMPLES_PER_WINDOW,
        "minimum_span_minutes_per_window_per_day": MINIMUM_WINDOW_SPAN_MINUTES,
    }
    for key, minimum in contract.items():
        try:
            actual = float(coverage.get(key))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"coverage contract is missing {key}") from exc
        if actual < minimum:
            raise ValueError(f"coverage contract {key} is weaker than {minimum}")
    qualifying_days = summary.get("qualifying_complete_days") or []
    if len(qualifying_days) < MINIMUM_DAYS:
        raise ValueError("measured summary has fewer than three qualifying complete days")
    if summary.get("statistics_scope") != "qualifying_complete_days_only":
        raise ValueError("measured statistics must exclude partial days")
    raw = summary.get("roundtrip_proxy_bps_by_notional") or {}
    scenarios = {}
    missing = [str(notional) for notional in TARGET_NOTIONALS_USDC
               if not raw.get(str(notional))]
    if missing:
        raise ValueError(f"missing required notional statistics: {', '.join(missing)}")
    for notional_int in TARGET_NOTIONALS_USDC:
        label = str(notional_int)
        stats = raw[label]
        if not stats:
            raise ValueError(f"missing roundtrip statistics for {label}")
        notional = float(notional_int)
        median = _finite_nonnegative(stats.get("median"), f"{label}.median")
        p95 = _finite_nonnegative(stats.get("p95"), f"{label}.p95")
        if p95 < median:
            raise ValueError(f"{label}.p95 cannot be below its median")
        stress_oracle_bps = oracle_locked_usdc / notional * 10_000
        scenarios[label] = {
            "notional_usdc": notional,
            "oracle_locked_usdc": oracle_locked_usdc,
            "oracle_net_usdc": {"base": 0.0, "conservative": 0.0,
                                "stress": oracle_locked_usdc},
            "stress_oracle_equivalent_bps": stress_oracle_bps,
            "base_roundtrip_bps": median,
            "conservative_roundtrip_bps": p95,
            "stress_roundtrip_bps": max(2 * median, p95) + stress_oracle_bps,
        }
    rollover = summary.get("rollover_pct_per_8h") or {}
    current_annual_cost_pct = {}
    for side in ("long", "short"):
        stats = rollover.get(side)
        if not stats:
            raise ValueError(f"missing rollover statistics for {side}")
        # Builder SDK getPairs() exposes display/PnL rate = -contract fee.
        # Negative display is therefore a cost; positive display is a credit.
        # Historical research never counts today's credit as backtest profit.
        rate = stats.get("median")
        try:
            rate = float(rate)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"rollover {side} median must be numeric") from exc
        if not math.isfinite(rate):
            raise ValueError(f"rollover {side} median must be finite")
        current_annual_cost_pct[side] = max(0.0, -rate) * 3 * 365.25
    carry = {
        "base_annual_cost_pct": current_annual_cost_pct,
        "conservative_annual_cost_pct": {
            side: max(8.0, value) for side, value in current_annual_cost_pct.items()},
        "stress_annual_cost_pct": {
            side: max(12.0, value) for side, value in current_annual_cost_pct.items()},
        "rollover_sign_semantics": "builder SDK display/PnL rate = negative contract fee",
        "credit_policy": "positive SDK display rate is capped at zero cost; no historical credit inferred"
    }
    return {"schema_version": 1, "decision": "PASS_COSTS_FROZEN",
            "costs_frozen": True, "qualifying_complete_days": qualifying_days,
            "scenario_definition": {
                "base": "median measured roundtrip proxy; successful full-close oracle refund",
                "conservative": "p95 measured roundtrip proxy; successful full-close oracle refund",
                "stress": "max(2*median,p95) proxy plus loss of the locked oracle amount"
            },
            "by_notional": scenarios, "carry": carry,
            "paper_authorized": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle-locked-usdc", type=float, default=0.10)
    args = parser.parse_args()
    raw = args.summary.read_bytes()
    result = derive(json.loads(raw), oracle_locked_usdc=args.oracle_locked_usdc)
    result["source_sha256"] = hashlib.sha256(raw).hexdigest()
    write_atomic(args.output, json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"decision": result["decision"],
                      "costs_frozen": result["costs_frozen"]}, indent=2))


if __name__ == "__main__":
    main()
