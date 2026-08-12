import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "lab/sq_bridge/ostium_markets.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_registry_matches_current_noncrypto_ostium_economics():
    markets = _load(REGISTRY)["markets"]
    for symbol in ("EURUSD", "USDJPY", "GBPUSD", "XAUUSD"):
        summary = _load(
            ROOT / f"data/ostium_economics_universe/{symbol.lower()}_ostium_execution_summary_latest.json"
        )
        market = markets[symbol]
        assert market["ostium_pair_id"] == summary["instrument"]["pair_id"]
        assert market["venue_max_leverage"] == summary["limits"]["max_leverage"]["p50"]
        assert market["minimum_notional_usdc"] == summary["limits"]["min_notional_usd"]["p50"]
        assert market["opening_fee_bps"] == summary["fees"]["open_fee_bps"]["p50"]
        assert market["closing_fee_bps"] == summary["fees"]["close_fee_bps"]["p50"]


def test_us500_registry_matches_observed_normalized_snapshot():
    markets = _load(REGISTRY)["markets"]
    snapshot = _load(
        ROOT / "lab/sq_bridge/evidence/spxusd_ostium_execution_normalized_20260809T221712Z.json"
    )
    market = markets["US500"]
    assert market["ostium_pair_id"] == snapshot["instrument"]["pair_id"]
    assert market["venue_max_leverage"] == snapshot["limits"]["max_leverage"]
    assert market["minimum_notional_usdc"] == snapshot["limits"]["min_notional_usd"]
    assert market["opening_fee_bps"] == snapshot["fees"]["open_fee_bps"]
    assert market["closing_fee_bps"] == snapshot["fees"]["close_fee_bps"]


def test_gbpusd_is_present_but_blocked_until_historical_gap_is_closed():
    gbp = _load(REGISTRY)["markets"]["GBPUSD"]
    assert gbp["research_eligible"] is False
    assert gbp["live_eligible"] is False
    assert "2024-2025 gap" in gbp["warning"]
