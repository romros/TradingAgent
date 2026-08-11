"""Validate the immutable market identity shared by Alquimia v4 workers."""
from __future__ import annotations

import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


TOKEN = re.compile(r"^[A-Z0-9]{2,16}$")
TIMEFRAME = re.compile(r"^(M[1-9][0-9]*|H[1-9][0-9]*|D1)$")
CATEGORIES = {"forex", "commodity", "crypto", "index", "stock"}


def validate(config: dict[str, Any]) -> dict[str, str]:
    market = config.get("market")
    if not isinstance(market, dict):
        raise ValueError("v4 worker market contract missing")
    required = (
        "symbol", "timeframe", "source_timezone", "ostium_pair_id",
        "ostium_pair_from", "ostium_pair_to", "ostium_category",
    )
    if any(not isinstance(market.get(key), str) or not market[key]
           for key in required):
        raise ValueError("v4 worker market contract fields missing")
    if (not TOKEN.fullmatch(market["symbol"])
            or not TIMEFRAME.fullmatch(market["timeframe"])
            or not TOKEN.fullmatch(market["ostium_pair_from"])
            or not TOKEN.fullmatch(market["ostium_pair_to"])
            or not market["ostium_pair_id"].isdigit()
            or market["ostium_category"] not in CATEGORIES):
        raise ValueError("v4 worker market contract invalid")
    try:
        ZoneInfo(market["source_timezone"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("v4 worker source timezone invalid") from exc
    return {key: market[key] for key in required}


def instrument_identity(market: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        market["ostium_pair_id"], market["ostium_pair_from"],
        market["ostium_pair_to"], market["ostium_category"],
    )
