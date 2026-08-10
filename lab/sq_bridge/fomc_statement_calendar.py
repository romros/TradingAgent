#!/usr/bin/env python3
"""Extract scheduled regular FOMC statement dates from official Fed pages."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

FED_BASE = "https://www.federalreserve.gov"
STATEMENT_RE = re.compile(
    r'href=["\'](?P<href>/newsevents/pressreleases/monetary(?P<day>20\d{6})a\.htm)["\']',
    re.IGNORECASE,
)
PANEL_RE = re.compile(
    r'<h5[^>]*panel-heading[^>]*>(?P<head>.*?)</h5>(?P<body>.*?)(?=<h5[^>]*panel-heading|\Z)',
    re.IGNORECASE | re.DOTALL,
)
EXCLUDED_HEADINGS = ("unscheduled", "cancelled", "notation vote", "conference call")
CURRENT_BLOCK_RE = re.compile(
    r'<div class="(?:row fomc-meeting|fomc-meeting--shaded row fomc-meeting)"[^>]*>',
    re.IGNORECASE,
)


def clean_markup(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def historical_regular_statements(text: str, year: int) -> list[dict]:
    rows = []
    for panel in PANEL_RE.finditer(text):
        heading = clean_markup(panel.group("head"))
        lowered = heading.lower()
        if "meeting" not in lowered or any(word in lowered for word in EXCLUDED_HEADINGS):
            continue
        links = list(STATEMENT_RE.finditer(panel.group("body")))
        if len(links) > 1:
            raise ValueError(f"multiple statements in regular panel: {heading}")
        if not links:
            continue
        match = links[0]
        if int(match.group("day")[:4]) != year:
            raise ValueError(f"statement year mismatch in {heading}")
        rows.append({"date": date.fromisoformat(
            f'{match.group("day")[:4]}-{match.group("day")[4:6]}-{match.group("day")[6:]}'
        ).isoformat(), "statement_url": FED_BASE + match.group("href"), "meeting_heading": heading})
    return rows


def current_calendar_statements(text: str, minimum_year: int = 2021,
                                maximum_year: int = 2026) -> list[dict]:
    rows = []
    for block in CURRENT_BLOCK_RE.split(text)[1:]:
        if not re.search(r"<strong>\s*Statement:\s*</strong>", block, re.IGNORECASE):
            continue
        matches = list(STATEMENT_RE.finditer(block))
        if len(matches) != 1:
            raise ValueError(f"expected one HTML statement in current meeting block, found {len(matches)}")
        match = matches[0]
        compact = match.group("day")
        year = int(compact[:4])
        if minimum_year <= year <= maximum_year:
            rows.append({"date": f"{compact[:4]}-{compact[4:6]}-{compact[6:]}",
                         "statement_url": FED_BASE + match.group("href"),
                         "meeting_heading": "current FOMC calendar regular meeting"})
    return rows


def build(historical: dict[int, tuple[Path, str]], current: tuple[Path, str],
          time_evidence: list[tuple[Path, str, str]] | None = None) -> dict:
    events = []
    sources = []
    for year, (path, url) in sorted(historical.items()):
        raw = path.read_bytes()
        rows = historical_regular_statements(raw.decode("utf-8"), year)
        events.extend(rows)
        sources.append({"year_scope": str(year), "url": url, "sha256": hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw), "regular_statements": len(rows)})
    current_path, current_url = current
    current_raw = current_path.read_bytes()
    current_rows = current_calendar_statements(current_raw.decode("utf-8"))
    events.extend(current_rows)
    sources.append({"year_scope": "2021-2026", "url": current_url,
                    "sha256": hashlib.sha256(current_raw).hexdigest(), "bytes": len(current_raw),
                    "regular_statements": len(current_rows)})
    time_sources = []
    for path, url, expected_day in time_evidence or []:
        raw = path.read_bytes()
        plain = clean_markup(raw.decode("utf-8"))
        expected_text = date.fromisoformat(expected_day).strftime("%B %d, %Y at 2:00 p.m.").replace(" 0", " ")
        if expected_text not in plain:
            raise ValueError(f"official 2:00 p.m. release evidence missing for {expected_day}")
        time_sources.append({"date": expected_day, "url": url,
                             "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                             "observed_release_time": "2:00 p.m. America/New_York"})
    unique = {row["date"]: row for row in events}
    if len(unique) != len(events):
        raise ValueError("duplicate statement dates across official sources")
    ordered = [unique[key] for key in sorted(unique)]
    for row in ordered:
        stamp = date.fromisoformat(row["date"])
        if stamp.weekday() >= 5:
            raise ValueError(f"weekend statement date: {stamp}")
        row.update({"event": "scheduled_regular_fomc_statement",
                    "release_time_assumption": "14:00 America/New_York",
                    "performance_accessed": False})
    counts = {}
    for row in ordered:
        counts[str(date.fromisoformat(row["date"]).year)] = counts.get(
            str(date.fromisoformat(row["date"]).year), 0) + 1
    return {"schema_version": 1, "authority": "Federal Reserve official FOMC calendars",
            "sources": sources, "events": ordered, "events_by_year": counts,
            "excluded_event_types": list(EXCLUDED_HEADINGS),
            "release_time_evidence": time_sources,
            "release_time_status": "CORROBORATED_OFFICIAL_2015_AND_2025" if len(time_sources) >= 2
                                   else "ASSUMPTION_REQUIRES_PRICE_ALIGNMENT_PREFLIGHT",
            "performance_accessed": False, "live_authorized": False}


def write_csv(result: dict, output: Path) -> None:
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("date", "event", "release_time_assumption",
                                                     "statement_url", "meeting_heading"))
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in result["events"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    historical = {year: (args.root / f"fomchistorical{year}.htm",
                         f"{FED_BASE}/monetarypolicy/fomchistorical{year}.htm")
                  for year in range(2015, 2021)}
    current = (args.root / "fomccalendars.htm", f"{FED_BASE}/monetarypolicy/fomccalendars.htm")
    time_evidence = [
        (args.root / "fomcpresconf20150318.htm",
         f"{FED_BASE}/monetarypolicy/fomcpresconf20150318.htm", "2015-03-18"),
        (args.root / "fomcpresconf20250319.htm",
         f"{FED_BASE}/monetarypolicy/fomcpresconf20250319.htm", "2025-03-19"),
    ]
    result = build(historical, current, time_evidence)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    write_csv(result, args.csv)
    print(json.dumps({"events": len(result["events"]), "events_by_year": result["events_by_year"],
                      "performance_accessed": result["performance_accessed"]}, indent=2))


if __name__ == "__main__":
    main()
