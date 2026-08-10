from lab.sq_bridge.spxusd_small_account_cost_gate import derive


def measured_summary():
    return {"schema_version": 2, "decision": "MEASURED",
            "statistics_scope": "qualifying_complete_days_only",
            "frozen_coverage_gate": {
                "pass": True, "minimum_distinct_open_days": 3,
                "minimum_samples_per_window_per_day": 20,
                "minimum_span_minutes_per_window_per_day": 30},
            "qualifying_complete_days": ["a", "b", "c"],
            "roundtrip_proxy_bps_by_notional": {
                str(notional): {"median": 3, "p95": 5, "maximum": 7}
                for notional in (60, 100, 200, 400, 500)},
            "rollover_pct_per_8h": {
                "long": {"median": -0.005}, "short": {"median": 0.002}}}


def test_incomplete_summary_blocks_without_costs():
    result = derive({"decision": "INSUFFICIENT_OPEN_SESSION_COVERAGE",
                     "frozen_coverage_gate": {"pass": False}})
    assert result["decision"] == "BLOCK_INSUFFICIENT_EXECUTION_COVERAGE"
    assert result["costs_frozen"] is False


def test_measured_summary_refunds_oracle_except_under_stress_and_caps_credit():
    result = derive(measured_summary())
    assert result["decision"] == "PASS_COSTS_FROZEN"
    assert result["by_notional"]["100"]["base_roundtrip_bps"] == 3
    assert result["by_notional"]["200"]["base_roundtrip_bps"] == 3
    assert result["by_notional"]["200"]["conservative_roundtrip_bps"] == 5
    assert result["by_notional"]["200"]["stress_roundtrip_bps"] == 11
    assert result["by_notional"]["200"]["oracle_net_usdc"] == {
        "base": 0, "conservative": 0, "stress": 0.1}
    assert result["carry"]["base_annual_cost_pct"]["long"] == 0
    assert round(result["carry"]["base_annual_cost_pct"]["short"], 4) == 2.1915


def test_measured_summary_without_200_usdc_notional_fails_closed():
    summary = measured_summary()
    del summary["roundtrip_proxy_bps_by_notional"]["200"]
    try:
        derive(summary)
    except ValueError as exc:
        assert "200" in str(exc)
    else:
        raise AssertionError("missing 200 USDC measurements must not freeze costs")


def test_invalid_percentiles_fail_closed():
    summary = measured_summary()
    summary["roundtrip_proxy_bps_by_notional"]["200"]["p95"] = 2
    try:
        derive(summary)
    except ValueError as exc:
        assert "p95" in str(exc)
    else:
        raise AssertionError("an invalid percentile ordering must not freeze costs")


def test_old_summary_without_temporal_coverage_contract_fails_closed():
    summary = measured_summary()
    summary["schema_version"] = 1
    try:
        derive(summary)
    except ValueError as exc:
        assert "version 2" in str(exc)
    else:
        raise AssertionError("an old count-only summary must not freeze costs")
