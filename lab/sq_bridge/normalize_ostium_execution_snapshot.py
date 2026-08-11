#!/usr/bin/env python3
"""Validate and normalize a read-only Ostium SPX execution snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def normalize(payload: dict[str, Any], *, source_sha256: str | None = None,
              expected_pair: tuple[str, str] | None = None) -> dict[str, Any]:
    source = payload.get("source") or {}
    if source.get("package") != "@ostium/builder-sdk":
        raise ValueError("snapshot source package must be @ostium/builder-sdk")
    if not isinstance(source.get("version"), str) or not source["version"].strip():
        raise ValueError("snapshot source version is required")
    if source.get("mode") != "read-only":
        raise ValueError("snapshot source must be read-only")
    builder_fee_bps = _number(source.get("builderFeeBps", 0), "source.builderFeeBps")
    if builder_fee_bps != 0:
        raise ValueError("research snapshots must use builderFeeBps=0")
    pair = payload.get("pair") or {}
    pair_from = str(pair.get("pairFrom", "")).upper()
    pair_to = str(pair.get("pairTo", "")).upper()
    if expected_pair:
        normalized_expected = tuple(value.upper() for value in expected_pair)
        if (pair_from, pair_to) != normalized_expected:
            raise ValueError(f"snapshot is not {normalized_expected[0]}/{normalized_expected[1]}")
    elif (pair_from, pair_to) not in {("US500", "USD"), ("SPX", "USD")}:
        raise ValueError("snapshot is not SPX/USD or US500/USD")

    mid = _number(pair.get("midPx"), "midPx")
    bid = _number(pair.get("bidPx"), "bidPx")
    ask = _number(pair.get("askPx"), "askPx")
    if not 0 < bid <= mid <= ask:
        raise ValueError("invalid bid/mid/ask ordering")
    spread_bps = (ask - bid) / mid * 10_000.0

    sim = payload.get("simulatedSlippage") or {}
    requested = [_number(value, "requestedNotionalsUsd")
                 for value in payload.get("requestedNotionalsUsd", [])]
    if (not requested or any(value <= 0 for value in requested)
            or len(set(requested)) != len(requested)):
        raise ValueError("requestedNotionalsUsd must contain unique positive notionals")
    normalized_sim: dict[str, list[dict[str, float]]] = {}
    for side in ("long", "short"):
        rows = []
        seen: set[float] = set()
        for row in sim.get(side, []):
            slippage_pct = _number(row.get("slippage"), f"{side}.slippage")
            notional = _number(row.get("ntl"), f"{side}.ntl")
            if notional <= 0 or notional in seen:
                raise ValueError(f"{side} slippage notionals must be unique and positive")
            if slippage_pct < 0:
                raise ValueError(f"{side}.slippage must be non-negative")
            seen.add(notional)
            rows.append({
                "notional_usd": notional,
                "slippage_pct": slippage_pct,
                "slippage_bps": slippage_pct * 100.0,
            })
        if seen != set(requested):
            raise ValueError(f"{side} slippage notionals do not match requestedNotionalsUsd")
        normalized_sim[side] = sorted(rows, key=lambda row: row["notional_usd"])

    rollover = pair.get("rolloverRate") or {}
    return {
        "schema_version": 1,
        "captured_at": payload.get("capturedAt"),
        "source": {
            "package": source.get("package"),
            "version": source.get("version"),
            "mode": source.get("mode"),
            "builder_fee_bps": builder_fee_bps,
            "raw_sha256": source_sha256,
        },
        "instrument": {
            "pair_id": str(pair.get("pairId")),
            "pair_from": pair_from,
            "pair_to": pair_to,
            "category": pair.get("category"),
        },
        "market_state": {
            "is_market_open": pair.get("isMarketOpen"),
            "is_day_trading_closed": pair.get("isDayTradingClosed"),
            "seconds_to_toggle_day_trading": pair.get("secondsToToggleIsDayTradingClosed"),
            "schedule": pair.get("schedule"),
        },
        "limits": {
            "min_size": _number(pair.get("minSz"), "minSz"),
            "min_notional_usd": _number(pair.get("minNtl"), "minNtl"),
            "max_buy_size": _number(pair.get("maxBSz"), "maxBSz"),
            "max_short_size": _number(pair.get("maxSSz"), "maxSSz"),
            "max_leverage": _number(pair.get("maxLeverage"), "maxLeverage"),
            "overnight_max_leverage": _number(
                pair.get("overnightMaxLeverage"), "overnightMaxLeverage"
            ),
            "overnight_zero_means_unrestricted": True,
        },
        "fees": {
            "open_fee_bps": _number(pair.get("openFee"), "openFee"),
            "close_fee_bps": _number(pair.get("closeFee"), "closeFee"),
            "rollover_long_pct_per_8h": _number(rollover.get("long"), "rolloverRate.long"),
            "rollover_short_pct_per_8h": _number(rollover.get("short"), "rolloverRate.short"),
            "rollover_fee_per_block_native": str(pair.get("rolloverFeePerBlock")),
        },
        "quote": {
            "mid": mid,
            "bid": bid,
            "ask": ask,
            "spread_bps": spread_bps,
        },
        "simulated_slippage": normalized_sim,
        "interpretation": {
            "spread_status": "OBSERVED_SINGLE_SNAPSHOT",
            "slippage_unit_status": "VERIFIED_PERCENT_FROM_SDK_TYPES_AND_FORMULAE",
            "slippage_spread_semantics": "PRICE_IMPACT_ALREADY_INCLUDES_BID_ASK_COMPONENT",
            "paper_gate": "BLOCKED_UNTIL_OPEN_MARKET_TIME_SERIES",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pair-from")
    parser.add_argument("--pair-to")
    args = parser.parse_args()
    raw_bytes = args.raw.read_bytes()
    if bool(args.pair_from) != bool(args.pair_to):
        parser.error("--pair-from and --pair-to must be supplied together")
    expected = (args.pair_from, args.pair_to) if args.pair_from else None
    result = normalize(json.loads(raw_bytes), source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
                       expected_pair=expected)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
