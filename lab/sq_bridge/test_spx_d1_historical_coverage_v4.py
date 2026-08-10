from datetime import date, timedelta

from lab.sq_bridge import spx_d1_historical_coverage_v4 as coverage


def test_weekdays_exclude_weekends():
    assert coverage.weekdays(date(2026, 8, 7), date(2026, 8, 10)) == [
        date(2026, 8, 7), date(2026, 8, 10)]


def test_coverage_only_policy_selects_suffix_after_latest_bad_year(tmp_path, monkeypatch):
    source = tmp_path / "source.parquet"
    source.write_bytes(b"frozen-source")
    first, last = date(2020, 1, 1), date(2022, 12, 30)
    complete = set(coverage.weekdays(first, last))
    # Make 2020 structurally unusable while 2021-2022 remain complete.
    complete -= set(coverage.weekdays(date(2020, 1, 1), date(2020, 10, 31)))
    monkeypatch.setattr(coverage, "complete_sessions", lambda _: (first, last, complete))
    result = coverage.audit(source)
    assert result["decision"] == "PASS_HISTORICAL_COVERAGE"
    assert result["selected_research_span"]["first"] == "2021-01-01"
    assert result["performance_accessed"] is False
    assert set(result["historical_period_coverage"]) == {"2021", "2022"}


def test_no_contiguous_eligible_suffix_blocks(tmp_path, monkeypatch):
    source = tmp_path / "source.parquet"
    source.write_bytes(b"frozen-source")
    first, last = date(2022, 1, 3), date(2022, 12, 30)
    all_days = coverage.weekdays(first, last)
    monkeypatch.setattr(coverage, "complete_sessions",
                        lambda _: (first, last, set(all_days[:20])))
    result = coverage.audit(source)
    assert result["decision"] == "BLOCK_HISTORICAL_COVERAGE"
    assert result["selected_research_span"] is None
