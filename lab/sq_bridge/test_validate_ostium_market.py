#!/usr/bin/env python3

from pathlib import Path

from validate_ostium_market import validate


registry = Path(__file__).with_name("ostium_markets.json")
result = validate(registry, "NVDA")
assert result["status"] == "PASS_RESEARCH"
assert result["mapping"]["ostium_pair"] == "NVDA/USD"
assert result["mapping"]["sq_symbol"] == "NVDAUSUSD_TICK_UTCMinus05"
assert result["live_authorized"] is False
print("PASS: Ostium synthetic-market gate")
