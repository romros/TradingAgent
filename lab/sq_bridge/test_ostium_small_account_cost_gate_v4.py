import pytest

from lab.sq_bridge.ostium_small_account_cost_gate_v4 import (
    REQUIRED_NOTIONALS_USDC, derive,
)


def summary(*, samples=30, days=3, hours=6):
    distribution = {"n": samples, "p50": 4.0, "p95": 6.0, "min": 3.0, "max": 8.0}
    return {
        "schema_version": 1,
        "instrument": {"pair_id": "2", "pair_from": "EUR", "pair_to": "USD",
                       "category": "forex"},
        "gate": {"execution_economics": "PASS" if samples >= 30 and days >= 3 and hours >= 6
                 else "INSUFFICIENT_OPEN_MARKET_EVIDENCE",
                 "checks": {"open_samples": {"actual": samples},
                            "distinct_utc_days": {"actual": days},
                            "distinct_utc_hours": {"actual": hours}}},
        "roundtrip_proxy_bps_by_notional": {
            str(notional): {"direction_neutral": dict(distribution),
                    "long": {**distribution, "p50": 3.5},
                    "short": {**distribution, "p50": 4.5}}
            for notional in REQUIRED_NOTIONALS_USDC},
        "fees": {"rollover_long_pct_per_8h": {"p50": -.002},
                 "rollover_short_pct_per_8h": {"p50": .002}},
        "limits": {"max_leverage": {"p50": 200}, "min_notional_usd": {"p50": 5}},
    }


def test_incomplete_evidence_blocks_without_freezing_provisional_values():
    result = derive(summary(samples=29), expected_pair_id="2", expected_pair=("EUR", "USD"))
    assert result["decision"] == "BLOCK_INSUFFICIENT_EXECUTION_COVERAGE"
    assert result["costs_frozen"] is False
    assert result["notional_observations"]["14000"] == 29
    assert result["remaining_complete_captures_lower_bound"] == 1
    assert "by_notional" not in result


def test_incomplete_evidence_exposes_the_slowest_notional_bucket():
    value = summary(samples=12, days=1, hours=4)
    value["roundtrip_proxy_bps_by_notional"]["14000"]["direction_neutral"]["n"] = 3
    result = derive(value, expected_pair_id="2", expected_pair=("EUR", "USD"))
    assert result["notional_observations"]["14000"] == 3
    assert result["remaining_complete_captures_lower_bound"] == 27


def test_mature_evidence_freezes_small_account_scenarios_and_oracle_semantics():
    result = derive(summary(), expected_pair_id="2", expected_pair=("EUR", "USD"))
    costs = result["by_notional"]["200"]
    assert result["decision"] == "PASS_COSTS_FROZEN"
    assert costs["base_roundtrip_bps"] == 4
    assert costs["conservative_roundtrip_bps"] == 6
    assert costs["stress_roundtrip_bps"] == 13  # 2*4 + 5 bps oracle
    assert costs["oracle_net_usdc"] == {"base": 0, "conservative": 0, "stress": .1}
    assert result["carry"]["long"]["sdk_display_pnl_pct_per_8h"] == -.002
    assert result["carry"]["long"]["derived_cost_pct_per_8h"] == .002
    assert round(result["carry"]["long"]["base_annual_cost_pct"], 4) == 2.1915
    assert result["carry"]["short"]["base_annual_cost_pct"] == 0
    assert result["paper_authorized"] is False


def test_identity_and_invalid_percentiles_fail_closed():
    with pytest.raises(ValueError, match="identity mismatch"):
        derive(summary(), expected_pair_id="5", expected_pair=("XAU", "USD"))
    invalid = summary()
    invalid["roundtrip_proxy_bps_by_notional"]["200"]["direction_neutral"]["p95"] = 2
    with pytest.raises(ValueError, match="below p50"):
        derive(invalid, expected_pair_id="2", expected_pair=("EUR", "USD"))


def test_global_maturity_cannot_hide_missing_high_notional_samples():
    value = summary()
    value["roundtrip_proxy_bps_by_notional"]["14000"]["direction_neutral"]["n"] = 29
    result = derive(value, expected_pair_id="2", expected_pair=("EUR", "USD"))
    assert result["decision"] == "BLOCK_INSUFFICIENT_NOTIONAL_COVERAGE"
    assert result["notional_observations"]["14000"] == 29
    assert "by_notional" not in result
