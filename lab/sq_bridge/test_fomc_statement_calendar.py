from pathlib import Path

from lab.sq_bridge.fomc_statement_calendar import (
    build, current_calendar_statements, historical_regular_statements,
)


def panel(heading, day):
    return (f'<h5 class="panel-heading">{heading}</h5><div>'
            f'<a href="/newsevents/pressreleases/monetary{day}a.htm">Statement</a></div>')


def current_block(day, labelled_statement=True):
    label = "<strong>Statement:</strong>" if labelled_statement else "Statement on Longer-Run Goals"
    return (f'<div class="row fomc-meeting">{label}'
            f'<a href="/newsevents/pressreleases/monetary{day}a.htm">HTML</a></div>')


def test_historical_parser_excludes_non_ex_ante_meetings():
    text = (panel("January 27-28 Meeting - 2020", "20200129")
            + panel("March 2 (unscheduled) Meeting - 2020", "20200303")
            + panel("March 17-18 (cancelled) Meeting - 2020", "20200318")
            + panel("March 31 (notation vote) - 2020", "20200331"))
    rows = historical_regular_statements(text, 2020)
    assert [row["date"] for row in rows] == ["2020-01-29"]


def test_manifest_has_hashes_and_never_claims_performance(tmp_path):
    from datetime import date, timedelta

    historical = {}
    for year in range(2015, 2021):
        day = date(year, 1, 1)
        day += timedelta(days=(2 - day.weekday()) % 7)
        path = tmp_path / f"{year}.htm"
        path.write_text(panel(f"January Meeting - {year}", day.strftime("%Y%m%d")))
        historical[year] = (path, f"https://fed.test/{year}")
    current = tmp_path / "current.htm"
    current.write_text(current_block("20210127") + current_block("20220126"))
    result = build(historical, (current, "https://fed.test/current"))
    assert len(result["events"]) == 8
    assert all(len(source["sha256"]) == 64 for source in result["sources"])
    assert result["performance_accessed"] is False
    assert all(row["performance_accessed"] is False for row in result["events"])
    assert result["release_time_status"] == "ASSUMPTION_REQUIRES_PRICE_ALIGNMENT_PREFLIGHT"


def test_two_official_release_pages_corroborate_1400_time(tmp_path):
    first = tmp_path / "first.htm"
    last = tmp_path / "last.htm"
    first.write_text("Released March 18, 2015 at 2:00 p.m.")
    last.write_text("Released March 19, 2025 at 2:00 p.m.")
    historical = {}
    for year in range(2015, 2021):
        path = tmp_path / f"h{year}.htm"
        path.write_text("")
        historical[year] = (path, f"https://fed.test/{year}")
    current = tmp_path / "current2.htm"
    current.write_text("")
    result = build(historical, (current, "https://fed.test/current"), [
        (first, "https://fed.test/first", "2015-03-18"),
        (last, "https://fed.test/last", "2025-03-19"),
    ])
    assert result["release_time_status"] == "CORROBORATED_OFFICIAL_2015_AND_2025"
    assert len(result["release_time_evidence"]) == 2


def test_statement_year_mismatch_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="year mismatch"):
        historical_regular_statements(panel("January Meeting - 2015", "20160101"), 2015)


def test_current_parser_excludes_non_meeting_policy_statement():
    text = current_block("20250129") + current_block("20250822", labelled_statement=False)
    assert [row["date"] for row in current_calendar_statements(text)] == ["2025-01-29"]
