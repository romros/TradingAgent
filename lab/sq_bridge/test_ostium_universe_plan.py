import json
from pathlib import Path

from lab.sq_bridge.ostium_universe_plan import build_plan


CATALOG = Path(__file__).with_name("ostium_research_universe_v2.json")


def test_universe_has_all_current_fx_metals_and_indices():
    catalog = json.loads(CATALOG.read_text())
    symbols = {item["symbol"] for item in catalog["markets"]}
    assert {"AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "USDCAD", "USDCHF",
            "USDJPY", "USDMXN", "USDKRW"} <= symbols
    assert {"XAUUSD", "XAGUSD", "XCUUSD", "XPTUSD", "XPDUSD"} <= symbols
    assert {"US500", "US100", "US30", "GER40", "UK100", "JP225", "HK50"} <= symbols


def test_plan_fails_closed_and_prioritizes_existing_evidence():
    plan = build_plan(json.loads(CATALOG.read_text()))
    assert plan["research_authorized"] == []
    by_symbol = {row["symbol"]: row for row in plan["queue"]}
    assert by_symbol["EURUSD"]["next_action"] == "REFRESH_PARITY"
    assert by_symbol["GBPUSD"]["next_action"] == "EXTEND_OSTIUM_OVERLAP_THEN_RECERTIFY"
    assert by_symbol["US500"]["next_action"] == "VERIFY_SOURCE_AND_MAPPING"
    assert all(not row["research_authorized"] for row in plan["queue"])
