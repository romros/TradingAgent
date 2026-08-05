from lab.sq_bridge.intraday_source_parity import (
    aggregate_close, compare, decide, decide_research_timeframe,
)


def test_identical_dense_series_passes_pilot():
    reference = {1_000 + 60 * i: 1.25 + i / 100_000 for i in range(1_200)}
    metrics = compare(reference, dict(reference))
    assert metrics["aligned_rows"] == 1_200
    assert metrics["close_diff_bps_p95"] == 0
    assert metrics["m1_return_correlation"] == 1
    assert decide(metrics)["decision"] == "PASS_PROXY_PILOT"


def test_timestamp_shift_and_price_divergence_fail_closed():
    reference = {1_000 + 60 * i: 1 + i / 100_000 for i in range(1_200)}
    ostium = {1_030 + 60 * i: 2 + i / 100_000 for i in range(1_200)}
    result = decide(compare(reference, ostium))
    assert result["decision"] == "BLOCK"
    assert "ALIGNED_ROWS_LT_1000" in result["reasons"]


def test_aggregation_uses_last_close_and_matching_interval():
    rows = {0: 100, 60: 101, 120: 102, 180: 103, 240: 104,
            300: 105, 360: 106, 420: 107, 480: 108, 540: 109,
            600: 110, 660: 111, 720: 112, 780: 113, 840: 114,
            900: 115, 960: 116, 1020: 117, 1080: 118, 1140: 119}
    aggregated = aggregate_close(rows, 5)
    assert aggregated == {0: 104, 300: 109, 600: 114, 900: 119}
    metrics = compare(aggregated, dict(aggregated), interval_seconds=300)
    assert metrics["consecutive_return_pairs"] == 3
    assert metrics["m1_return_correlation"] == 1


def test_research_timeframe_requires_sample_and_quality():
    good = {
        "aligned_rows": 48, "union_coverage_ratio": 1,
        "m1_return_correlation": .99, "return_direction_match_ratio": .98,
        "close_diff_bps_p95": 2,
    }
    assert decide_research_timeframe(good, 40)["pass"] is True
    result = decide_research_timeframe(good, 100)
    assert result["pass"] is False
    assert "ALIGNED_ROWS_LT_100" in result["reasons"]
