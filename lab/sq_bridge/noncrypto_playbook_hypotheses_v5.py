#!/usr/bin/env python3
"""Validate the performance-blind non-crypto playbook hypothesis catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CATALOG = Path(__file__).with_name("noncrypto_playbook_hypotheses_v5.json")
ALLOWED_MARKETS = {"EURUSD", "USDJPY", "XAUUSD", "US500"}
ALLOWED_TIMEFRAMES = {"M15", "D1"}


def validate(path: Path = CATALOG) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("stage") != "PREPERFORMANCE_HYPOTHESIS":
        raise ValueError("catalog is not preperformance")
    for field in ("performance_accessed", "holdout_accessed", "legacy_candidates_reused", "daily_profit_promise"):
        if doc.get(field) is not False:
            raise ValueError(f"{field} must be false")
    common = doc.get("common_invariants", {})
    if common.get("entry_timing") != "NEXT_BAR_OPEN":
        raise ValueError("entry must be next-bar open")
    if common.get("stop_can_only_tighten") is not True:
        raise ValueError("protective stop invariant missing")
    if common.get("minimum_gross_move_over_provisional_cost_p95", 0) < 3:
        raise ValueError("cost hurdle is too weak")

    seen: set[str] = set()
    markets: set[str] = set()
    families: set[str] = set()
    items = doc.get("hypotheses", [])
    if not 3 <= len(items) <= 6:
        raise ValueError("catalog must contain 3-6 hypotheses")
    for item in items:
        hypothesis_id = item["hypothesis_id"]
        if hypothesis_id in seen:
            raise ValueError(f"duplicate hypothesis: {hypothesis_id}")
        seen.add(hypothesis_id)
        market = item["market"]
        if market not in ALLOWED_MARKETS:
            raise ValueError(f"market not authorized by Check 2: {market}")
        if item["timeframe"] not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"timeframe not authorized: {item['timeframe']}")
        if not item.get("context_required") or not item.get("context_veto"):
            raise ValueError(f"context contract incomplete: {hypothesis_id}")
        if not item.get("initial_stop") or not item.get("take_profit"):
            raise ValueError(f"exit contract incomplete: {hypothesis_id}")
        holding = item.get("max_holding_bars_range", [])
        if len(holding) != 2 or not 0 < holding[0] <= holding[1] <= 20:
            raise ValueError(f"invalid holding range: {hypothesis_id}")
        if "NONE" not in item.get("fast_manager_variants", []):
            raise ValueError(f"unmanaged baseline missing: {hypothesis_id}")
        if not item.get("falsification"):
            raise ValueError(f"falsification rule missing: {hypothesis_id}")
        markets.add(market)
        families.add(item["family"])
    return {
        "decision": "PASS_PREPERFORMANCE_HYPOTHESIS_CATALOG",
        "hypothesis_count": len(items),
        "markets": sorted(markets),
        "family_count": len(families),
        "performance_accessed": False,
        "holdout_accessed": False,
        "legacy_candidates_reused": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2, sort_keys=True))
