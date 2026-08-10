#!/usr/bin/env python3
"""Extract upcoming regular FOMC decision dates from the official current calendar."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

FED_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
YEAR_RE = re.compile(r"<h4><a[^>]*>(?P<year>20\d{2}) FOMC Meetings</a></h4>", re.IGNORECASE)
BLOCK_RE = re.compile(
    r'<div class="(?:row fomc-meeting|fomc-meeting--shaded row fomc-meeting)"[^>]*>',
    re.IGNORECASE,
)
MONTH_RE = re.compile(r'fomc-meeting__month[^>]*>\s*<strong>(?P<month>[A-Za-z]+)</strong>',
                      re.IGNORECASE)
DATE_RE = re.compile(r'fomc-meeting__date[^>]*>(?P<days>[^<]+)</div>', re.IGNORECASE)
MONTHS = {name: number for number, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"), start=1)}


def _clean(value: str) -> str:
    return " ".join(html.unescape(value).split())


def extract(text: str, as_of: date) -> list[dict]:
    starts = list(YEAR_RE.finditer(text))
    rows = []
    for index, year_match in enumerate(starts):
        year = int(year_match.group("year"))
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        section = text[year_match.end():end]
        for block in BLOCK_RE.split(section)[1:]:
            month_match, date_match = MONTH_RE.search(block), DATE_RE.search(block)
            if not month_match or not date_match:
                continue
            day_label = _clean(date_match.group("days"))
            lowered = day_label.lower()
            if any(token in lowered for token in ("notation vote", "unscheduled", "cancelled")):
                continue
            day_numbers = [int(value) for value in re.findall(r"\d+", day_label)]
            if not day_numbers:
                raise ValueError(f"meeting date has no day number: {day_label}")
            month_name = month_match.group("month").title()
            if month_name not in MONTHS:
                raise ValueError(f"unknown month: {month_name}")
            decision_date = date(year, MONTHS[month_name], day_numbers[-1])
            rows.append({"decision_date": decision_date.isoformat(), "year": year,
                         "month": month_name, "meeting_days_label": day_label,
                         "scheduled_regular": True,
                         "assumed_statement_time": "14:00 America/New_York",
                         "future_as_of_capture": decision_date > as_of})
    unique = {row["decision_date"]: row for row in rows}
    if len(unique) != len(rows):
        raise ValueError("duplicate scheduled decision dates")
    return [unique[key] for key in sorted(unique)]


def build(path: Path, as_of: date) -> dict:
    raw = path.read_bytes()
    meetings = extract(raw.decode("utf-8"), as_of)
    upcoming = [row for row in meetings if row["future_as_of_capture"]]
    return {"schema_version": 1, "authority": "Federal Reserve official current FOMC calendar",
            "source_url": FED_URL, "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw), "as_of": as_of.isoformat(), "meetings": meetings,
            "upcoming_meetings": upcoming,
            "next_scheduled_decision_date": upcoming[0]["decision_date"] if upcoming else None,
            "performance_accessed": False, "live_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.input, args.as_of)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"as_of": result["as_of"],
                      "next_scheduled_decision_date": result["next_scheduled_decision_date"],
                      "upcoming_count": len(result["upcoming_meetings"]),
                      "performance_accessed": result["performance_accessed"]}, indent=2))


if __name__ == "__main__":
    main()
