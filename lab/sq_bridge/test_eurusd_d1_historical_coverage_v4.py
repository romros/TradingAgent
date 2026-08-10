from datetime import date, timedelta

from lab.sq_bridge.eurusd_d1_historical_coverage_v4 import evaluate


def _weekdays(start, end):
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def test_coverage_selects_longest_suffix_without_performance():
    rows = [(day, 1440) for day in _weekdays(date(2020, 1, 1), date(2022, 12, 31))]
    rows = [(day, 100 if day.year == 2020 and day.month <= 6 else minutes)
            for day, minutes in rows]
    result = evaluate(rows, {"manifest_sha256": "a" * 64})
    assert result["decision"] == "PASS_HISTORICAL_COVERAGE"
    assert result["selected_research_span"]["first"] == "2021-01-01"
    assert result["performance_accessed"] is False


def test_coverage_blocks_when_latest_year_is_incomplete():
    rows = [(day, 100) for day in _weekdays(date(2022, 1, 1), date(2022, 12, 31))]
    result = evaluate(rows, {"manifest_sha256": "b" * 64})
    assert result["decision"] == "BLOCK_HISTORICAL_COVERAGE"
    assert result["selected_research_span"] is None
