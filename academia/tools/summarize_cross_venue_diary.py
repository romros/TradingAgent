#!/usr/bin/env python3
"""Summarize temporary hourly cross-venue snapshots into daily evidence."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median


def finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize(rows: list[dict]) -> dict:
    cells: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    for row in rows:
        day = str(row["captured_at"])[:10]
        for source, message in row.get("errors", {}).items():
            if message:
                errors[f"{day}:{source}"] += 1
        for source, markets in row.get("sources", {}).items():
            for market in markets:
                contract = market.get("venue_contract") or market.get("instrument")
                if contract:
                    cells[(day, source, contract)].append(market)

    days: dict[str, dict] = defaultdict(dict)
    for (day, source, contract), items in sorted(cells.items()):
        def values(name):
            return [number for item in items if (number := finite(item.get(name))) is not None]

        prices = values("mid") or values("mark")
        spreads = values("spread_bps") or values("impact_spread_bps")
        funding = values("funding_raw")
        oi = values("open_interest_base")
        basis = []
        for item in items:
            mark, oracle = finite(item.get("mark")), finite(item.get("oracle"))
            if mark is not None and oracle not in (None, 0):
                basis.append((mark - oracle) / oracle * 10_000)
        opened = [item.get("market_open") for item in items if isinstance(item.get("market_open"), bool)]
        days[day][f"{source}:{contract}"] = {
            "snapshots": len(items),
            "market_open_share": None if not opened else sum(opened) / len(opened),
            "price_first": None if not prices else prices[0],
            "price_last": None if not prices else prices[-1],
            "return_pct": None if len(prices) < 2 or prices[0] == 0 else (prices[-1] / prices[0] - 1) * 100,
            "spread_bps_median": None if not spreads else median(spreads),
            "spread_bps_maximum": None if not spreads else max(spreads),
            "mark_oracle_basis_bps_median": None if not basis else median(basis),
            "funding_raw_median": None if not funding else median(funding),
            "funding_raw_minimum": None if not funding else min(funding),
            "funding_raw_maximum": None if not funding else max(funding),
            "open_interest_first": None if not oi else oi[0],
            "open_interest_last": None if not oi else oi[-1],
            "open_interest_change_pct": None if len(oi) < 2 or oi[0] == 0 else (oi[-1] / oi[0] - 1) * 100,
            "last_24h_notional_volume_usd": next((number for item in reversed(items)
                if (number := finite(item.get("day_notional_volume_usd"))) is not None), None),
        }
    return {
        "schema_version": 1,
        "snapshot_rows": len(rows),
        "days": dict(days),
        "errors_by_day_and_source": dict(sorted(errors.items())),
        "cross_venue_basis_authorized": False,
        "decision": "OBSERVATION_ONLY_UNTIL_MAPPING_AND_FORWARD_GATES_PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    rendered = json.dumps(summarize(rows), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
