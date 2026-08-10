from lab.sq_bridge.ostium_execution_universe_gate import build


def summary(symbol, pair_id, samples, gate):
    pair_from, pair_to = symbol.split("/")
    return {
        "instrument": {"pair_from": pair_from, "pair_to": pair_to,
                       "pair_id": pair_id, "category": "forex"},
        "open_market_snapshots": samples,
        "spread_bps": {"p50": 1, "p95": 2},
        "fees": {
            "open_fee_bps": {"p50": 2},
            "rollover_long_pct_per_8h": {"p50": .01},
            "rollover_short_pct_per_8h": {"p50": -.02},
        },
        "limits": {"max_leverage": {"p50": 100}, "min_notional_usd": {"p50": 5}},
        "gate": {"execution_economics": gate, "checks": {
            "distinct_utc_days": {"actual": 3}, "distinct_utc_hours": {"actual": 6}}},
    }


def test_provisional_observation_never_unlocks_multiday_or_paper():
    result = build([summary("USD/JPY", "4", 1, "INSUFFICIENT_OPEN_MARKET_EVIDENCE")],
                   {"USD/JPY"})
    market = result["markets"]["USD/JPY"]
    assert market["research_cost_observation"] == "OBSERVED_PROVISIONAL"
    assert market["multiday_research"] == "BLOCKED_ROLLOVER_SERIES"
    assert market["paper"] == "BLOCKED_EXECUTION_ECONOMICS"
    assert result["live_authorized"] is False


def test_only_full_gate_marks_cost_model_ready():
    result = build([summary("USD/JPY", "4", 30, "PASS")], {"USD/JPY"})
    assert result["execution_ready_symbols"] == ["USD/JPY"]
    assert result["markets"]["USD/JPY"]["multiday_research"] == "COST_MODEL_READY"
    assert result["decision"] == "PASS_ALL_EXECUTION_GATES"


def test_expected_universe_mismatch_is_explicit():
    result = build([summary("USD/JPY", "4", 30, "PASS")], {"USD/JPY", "GBP/USD"})
    assert result["all_expected_present"] is False
    assert result["missing_symbols"] == ["GBP/USD"]
    assert result["decision"] == "COLLECT_MORE_OPEN_MARKET_EVIDENCE"


def test_duplicate_pair_is_rejected():
    import pytest
    row = summary("USD/JPY", "4", 30, "PASS")
    with pytest.raises(ValueError, match="duplicate summary"):
        build([row, row])
