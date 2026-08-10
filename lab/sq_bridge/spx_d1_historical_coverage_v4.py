#!/usr/bin/env python3
"""Coverage-only selection of a contiguous SPX D1 research history for v4."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb


EXPECTED_MINUTES = 390
MINIMUM_COMPLETE_SESSION_RATIO = 0.95
MINIMUM_OVERALL_COVERAGE_RATIO = 0.90
MINIMUM_EACH_YEAR_COVERAGE_RATIO = 0.80


def weekdays(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() < 5]


def complete_sessions(path: Path) -> tuple[date, date, set[date]]:
    rows = duckdb.connect(":memory:").execute(
        """WITH localized AS (
          SELECT CAST(timezone('America/New_York', to_timestamp(ts)) AS DATE) AS day,
                 CAST(timezone('America/New_York', to_timestamp(ts)) AS TIME) AS minute
          FROM read_parquet(?)
        ), regular AS (
          SELECT day, count(DISTINCT minute) AS observed_minutes
          FROM localized
          WHERE minute >= TIME '09:30:00' AND minute < TIME '16:00:00'
            AND dayofweek(day) BETWEEN 1 AND 5
          GROUP BY day
        )
        SELECT day, observed_minutes FROM regular ORDER BY day""",
        [str(path)],
    ).fetchall()
    if not rows:
        raise ValueError("source contains no New York regular-session observations")
    complete = {day for day, minutes in rows
                if minutes / EXPECTED_MINUTES >= MINIMUM_COMPLETE_SESSION_RATIO}
    return rows[0][0], rows[-1][0], complete


def audit(path: Path) -> dict:
    first, last, complete = complete_sessions(path)
    by_year = {}
    for year in range(first.year, last.year + 1):
        start = max(first, date(year, 1, 1))
        end = min(last, date(year, 12, 31))
        expected = weekdays(start, end)
        count = sum(day in complete for day in expected)
        by_year[str(year)] = {
            "from": start.isoformat(), "to": end.isoformat(),
            "expected_weekdays": len(expected), "complete_sessions": count,
            "coverage_ratio": count / len(expected) if expected else 0.0,
        }

    # Coverage, never performance, chooses the longest suffix ending at the
    # latest available observation whose every calendar segment clears 80%.
    eligible_start_year = None
    for candidate in range(first.year, last.year + 1):
        selected = [by_year[str(year)] for year in range(candidate, last.year + 1)]
        if all(row["coverage_ratio"] >= MINIMUM_EACH_YEAR_COVERAGE_RATIO
               for row in selected):
            eligible_start_year = candidate
            break
    selected_start = max(first, date(eligible_start_year, 1, 1)) if eligible_start_year else None
    selected_expected = weekdays(selected_start, last) if selected_start else []
    selected_complete = sum(day in complete for day in selected_expected)
    overall = selected_complete / len(selected_expected) if selected_expected else 0.0
    minimum_year = (min(by_year[str(year)]["coverage_ratio"]
                        for year in range(eligible_start_year, last.year + 1))
                    if eligible_start_year else 0.0)
    passed = (eligible_start_year is not None
              and overall >= MINIMUM_OVERALL_COVERAGE_RATIO
              and minimum_year >= MINIMUM_EACH_YEAR_COVERAGE_RATIO)
    return {
        "schema_version": 1,
        "performance_accessed": False,
        "source": {"path": str(path), "bytes": path.stat().st_size,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "regular_session": {"timezone": "America/New_York", "start": "09:30",
                            "end_exclusive": "16:00", "expected_minutes": EXPECTED_MINUTES,
                            "minimum_complete_session_ratio": MINIMUM_COMPLETE_SESSION_RATIO},
        "available_observation_span": {"first": first.isoformat(), "last": last.isoformat()},
        "coverage_by_calendar_year": by_year,
        "selection_policy": "longest suffix ending at latest observation with every calendar segment >= 0.80; no performance",
        "selected_research_span": ({"first": selected_start.isoformat(), "last": last.isoformat()}
                                   if selected_start else None),
        "historical_expected_observations": len(selected_expected),
        "historical_complete_observations": selected_complete,
        "historical_overall_coverage_ratio": overall,
        "historical_minimum_period_coverage_ratio": minimum_year,
        "historical_period_coverage": {
            str(year): by_year[str(year)]["coverage_ratio"]
            for year in range(eligible_start_year, last.year + 1)
        } if eligible_start_year else {},
        "historical_coverage_pass": passed,
        "decision": "PASS_HISTORICAL_COVERAGE" if passed else "BLOCK_HISTORICAL_COVERAGE",
        "research_only": True, "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "decision", "selected_research_span", "historical_expected_observations",
        "historical_complete_observations", "historical_overall_coverage_ratio",
        "historical_minimum_period_coverage_ratio")}, indent=2))


if __name__ == "__main__":
    main()
