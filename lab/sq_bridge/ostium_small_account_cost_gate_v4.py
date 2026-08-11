#!/usr/bin/env python3
"""Freeze small-account cost scenarios from a mature generic Ostium summary."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from lab.sq_bridge.us500_d1_market_preflight_v4 import write_atomic


MINIMUM_SAMPLES = 30
MINIMUM_DAYS = 3
MINIMUM_UTC_HOURS = 6
REQUIRED_NOTIONALS_USDC = (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 14000)


def number(value: Any, label: str, *, nonnegative: bool = True) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{label} must be finite" + (" and non-negative" if nonnegative else ""))
    return result


def derive(summary: dict[str, Any], *, expected_pair_id: str,
           expected_pair: tuple[str, str], oracle_locked_usdc: float = .10) -> dict[str, Any]:
    instrument, checks = summary.get("instrument") or {}, (summary.get("gate") or {}).get("checks") or {}
    identity = (str(instrument.get("pair_id")), str(instrument.get("pair_from")),
                str(instrument.get("pair_to")))
    if identity != (str(expected_pair_id), *expected_pair):
        raise ValueError(f"instrument identity mismatch: {identity}")
    requirements = {"open_samples": MINIMUM_SAMPLES, "distinct_utc_days": MINIMUM_DAYS,
                    "distinct_utc_hours": MINIMUM_UTC_HOURS}
    actual = {key: int((checks.get(key) or {}).get("actual", 0)) for key in requirements}
    raw = summary.get("roundtrip_proxy_bps_by_notional") or {}
    notional_coverage = {
        str(notional): int((((raw.get(str(notional)) or {}).get("direction_neutral") or {})
                           .get("n", 0)))
        for notional in REQUIRED_NOTIONALS_USDC
    }
    remaining_complete_captures = max(
        max(0, MINIMUM_SAMPLES - actual["open_samples"]),
        *(max(0, MINIMUM_SAMPLES - count) for count in notional_coverage.values()),
    )
    mature = ((summary.get("gate") or {}).get("execution_economics") == "PASS"
              and all(actual[key] >= minimum for key, minimum in requirements.items()))
    if not mature:
        return {"schema_version": 1, "decision": "BLOCK_INSUFFICIENT_EXECUTION_COVERAGE",
                "costs_frozen": False, "coverage": {key: {"actual": actual[key],
                "required": requirements[key]} for key in requirements},
                "required_notional_observations": MINIMUM_SAMPLES,
                "notional_observations": notional_coverage,
                "remaining_complete_captures_lower_bound": remaining_complete_captures,
                "paper_authorized": False, "live_authorized": False}
    if summary.get("schema_version") != 1:
        raise ValueError("execution summary must use schema_version=1")
    independence = summary.get("independence_filter") or {}
    independent_count = summary.get("open_market_snapshots")
    raw_count = summary.get("raw_open_market_snapshots")
    if (not isinstance(independent_count, int) or isinstance(independent_count, bool)
            or not isinstance(raw_count, int) or isinstance(raw_count, bool)
            or independent_count != actual["open_samples"]
            or raw_count < independent_count
            or independence.get("minimum_sample_spacing_seconds", 0) < 900
            or not isinstance(independence.get("exact_duplicate_snapshots_ignored"), int)
            or not isinstance(independence.get("too_close_snapshots_ignored"), int)):
        raise ValueError("execution summary lacks independent-sample proof")
    oracle = number(oracle_locked_usdc, "oracle_locked_usdc")
    if any(count < MINIMUM_SAMPLES for count in notional_coverage.values()):
        return {
            "schema_version": 1,
            "decision": "BLOCK_INSUFFICIENT_NOTIONAL_COVERAGE",
            "costs_frozen": False,
            "coverage": actual,
            "required_notional_observations": MINIMUM_SAMPLES,
            "notional_observations": notional_coverage,
            "remaining_complete_captures_lower_bound": remaining_complete_captures,
            "maximum_feasible_notional_usdc": max(REQUIRED_NOTIONALS_USDC),
            "paper_authorized": False,
            "live_authorized": False,
        }
    scenarios = {}
    for label, routes in raw.items():
        notional = number(label, f"notional {label}")
        neutral = routes.get("direction_neutral") or {}
        median = number(neutral.get("p50"), f"{label}.p50")
        p95 = number(neutral.get("p95"), f"{label}.p95")
        if p95 < median:
            raise ValueError(f"{label}.p95 cannot be below p50")
        stress_oracle_bps = oracle / notional * 10_000
        scenarios[label] = {
            "notional_usdc": notional, "observations": int(neutral.get("n", 0)),
            "oracle_locked_usdc": oracle,
            "oracle_net_usdc": {"base": 0.0, "conservative": 0.0, "stress": oracle},
            "base_variable_roundtrip_bps": median,
            "conservative_variable_roundtrip_bps": p95,
            "stress_variable_roundtrip_bps": max(2 * median, p95),
            "base_roundtrip_bps": median,
            "conservative_roundtrip_bps": p95,
            "stress_roundtrip_bps": max(2 * median, p95) + stress_oracle_bps,
            "long_route_p50_bps": number((routes.get("long") or {}).get("p50"), f"{label}.long.p50"),
            "short_route_p50_bps": number((routes.get("short") or {}).get("p50"), f"{label}.short.p50"),
        }
    fees = summary.get("fees") or {}
    carry = {}
    for side in ("long", "short"):
        rate = number((fees.get(f"rollover_{side}_pct_per_8h") or {}).get("p50"),
                      f"rollover_{side}", nonnegative=False)
        # Builder SDK getPairs() exposes a display/PnL rate, not the signed
        # contract fee: its formatter explicitly uses display = -contract.
        # Therefore a negative display rate is a cost and a positive one a
        # credit. Never extrapolate a current credit backwards as alpha.
        cost_rate = max(0.0, -rate)
        carry[side] = {
            "sdk_display_pnl_pct_per_8h": rate,
            "derived_cost_pct_per_8h": cost_rate,
            "base_annual_cost_pct": cost_rate * 3 * 365.25,
            "conservative_annual_cost_pct": max(8.0, cost_rate * 3 * 365.25),
            "stress_annual_cost_pct": max(12.0, cost_rate * 3 * 365.25),
        }
    return {
        "schema_version": 1, "decision": "PASS_COSTS_FROZEN", "costs_frozen": True,
        "instrument": instrument, "coverage": actual,
        "independent_sample_proof": {
            "raw_open_market_snapshots": raw_count,
            "independent_open_market_snapshots": independent_count,
            **independence,
        },
        "scenario_definition": {
            "base": "median measured direction-neutral roundtrip; oracle refunded",
            "conservative": "p95 measured direction-neutral roundtrip; oracle refunded",
            "stress": "max(2*median,p95) plus non-refunded 0.10 USDC oracle",
        },
        "required_notional_grid_usdc": list(REQUIRED_NOTIONALS_USDC),
        "maximum_feasible_notional_usdc": max(REQUIRED_NOTIONALS_USDC),
        "by_notional": scenarios, "carry": carry,
        "venue_limits": summary.get("limits"),
        "rollover_sign_semantics": "builder SDK display/PnL rate = negative contract fee",
        "credit_policy": "positive SDK display rate is capped at zero cost; no historical credit inferred",
        "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--pair-from", required=True)
    parser.add_argument("--pair-to", required=True)
    parser.add_argument("--oracle-locked-usdc", type=float, default=.10)
    args = parser.parse_args()
    raw = args.summary.read_bytes()
    result = derive(json.loads(raw), expected_pair_id=args.pair_id,
                    expected_pair=(args.pair_from, args.pair_to),
                    oracle_locked_usdc=args.oracle_locked_usdc)
    result["source_sha256"] = hashlib.sha256(raw).hexdigest()
    write_atomic(args.output, result)
    print(json.dumps({"decision": result["decision"],
                      "costs_frozen": result["costs_frozen"]}, indent=2))


if __name__ == "__main__":
    main()
