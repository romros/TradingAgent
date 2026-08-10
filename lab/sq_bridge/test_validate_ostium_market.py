#!/usr/bin/env python3

import json
from pathlib import Path
import subprocess

from validate_ostium_market import validate


registry = Path(__file__).with_name("ostium_markets.json")
result = validate(registry, "NVDA")
assert result["status"] == "PASS_RESEARCH"
assert result["mapping"]["ostium_pair"] == "NVDA/USD"
assert result["mapping"]["sq_symbol"] == "NVDAUSUSD_TICK_UTCMinus05"
assert result["live_authorized"] is False
print("PASS: Ostium synthetic-market gate")


def test_cli_can_persist_preflight_receipt(tmp_path):
    output = tmp_path / "preflight.json"
    subprocess.run(
        [
            "python3", "-m", "lab.sq_bridge.validate_ostium_market", "XAUUSD",
            "--output", str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["status"] == "PASS_RESEARCH"
    assert receipt["market"] == "XAUUSD"
    assert receipt["live_authorized"] is False


def test_crypto_registry_matches_current_ostium_caps_and_remains_not_live():
    eth = validate(registry, "ETHUSD"); sol = validate(registry, "SOLUSD")
    assert eth["mapping"]["opening_fee_bps"] == 10 and eth["mapping"]["venue_max_leverage"] == 200
    assert sol["mapping"]["opening_fee_bps"] == 10 and sol["mapping"]["venue_max_leverage"] == 150
    assert eth["live_authorized"] is False and sol["live_authorized"] is False
