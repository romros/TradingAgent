from datetime import date
from pathlib import Path

from lab.sq_bridge.fomc_upcoming_schedule import build, extract


def year(year_value, blocks):
    return f'<h4><a id="x">{year_value} FOMC Meetings</a></h4>{blocks}'


def block(month, days, shaded=False):
    classes = "fomc-meeting--shaded row fomc-meeting" if shaded else "row fomc-meeting"
    return (f'<div class="{classes}"><div class="fomc-meeting__month"><strong>{month}</strong></div>'
            f'<div class="fomc-meeting__date">{days}</div></div>')


def test_extracts_last_meeting_day_and_excludes_notation_votes():
    text = year(2026, block("July", "28-29") + block("September", "15-16*", True)
                + block("October", "27-28") + block("December", "8-9*", True)
                + block("August", "22 (notation vote)"))
    rows = extract(text, date(2026, 8, 10))
    assert [row["decision_date"] for row in rows] == [
        "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
    assert [row["decision_date"] for row in rows if row["future_as_of_capture"]] == [
        "2026-09-16", "2026-10-28", "2026-12-09"]


def test_build_hashes_source_and_never_accesses_performance(tmp_path):
    source = tmp_path / "calendar.htm"
    source.write_text(year(2026, block("September", "15-16*")))
    result = build(source, date(2026, 8, 10))
    assert len(result["source_sha256"]) == 64
    assert result["next_scheduled_decision_date"] == "2026-09-16"
    assert result["performance_accessed"] is False
    assert result["live_authorized"] is False
