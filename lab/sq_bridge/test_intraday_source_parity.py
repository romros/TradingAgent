from lab.sq_bridge.intraday_source_parity import (
    aggregate_close, apply_symmetric_bucket_exclusions, compare, compare_ohlcv,
    decide, decide_complete_ohlcv_timeframe, decide_research_timeframe,
    restrict_to_common_span,
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


def test_ohlcv_comparison_uses_only_complete_bars():
    reference = [
        {"ts": i * 60, "open": 100 + i, "high": 101 + i,
         "low": 99 + i, "close": 100.5 + i, "volume": 1}
        for i in range(6)
    ]
    ostium = [dict(row) for row in reference]
    result = compare_ohlcv(reference, ostium, 5)
    assert result["reference_bars_total"] == 2
    assert result["reference_bars_complete"] == 1
    assert result["aligned_complete_bars"] == 1
    assert result["fields"]["high"]["diff_bps_p95"] == 0


def test_complete_ohlcv_gate_does_not_pass_partial_bucket_coverage():
    metrics = {
        "aligned_complete_bars": 48,
        "close_returns": {
            "aligned_rows": 48, "union_coverage_ratio": .90,
            "m1_return_correlation": .999, "return_direction_match_ratio": 1,
            "close_diff_bps_p95": 1,
        },
    }
    result = decide_complete_ohlcv_timeframe(metrics, 40)
    assert result["pass"] is False
    assert "UNION_COVERAGE_LT_0_95" in result["reasons"]


def test_bucket_quarantine_is_applied_symmetrically():
    reference = [{"ts": ts} for ts in (0, 60, 3600, 3660)]
    ostium = [{"ts": ts} for ts in (0, 60, 3600)]
    clean_reference, clean_ostium = apply_symmetric_bucket_exclusions(
        reference, ostium, bucket_starts={0}, bucket_minutes=60,
    )
    assert [row["ts"] for row in clean_reference] == [3600, 3660]
    assert [row["ts"] for row in clean_ostium] == [3600]


def test_common_span_removes_only_tails_not_internal_gaps():
    reference = [{"ts": value} for value in (0, 60, 120, 180)]
    ostium = [{"ts": value} for value in (60, 180, 240)]
    left, right, span = restrict_to_common_span(reference, ostium)
    assert [row["ts"] for row in left] == [60, 120, 180]
    assert [row["ts"] for row in right] == [60, 180]
    assert span == {"from_ts": 60, "to_ts": 180}
