#!/usr/bin/env python3
"""Coverage-only audit of Dukascopy EURUSD D1 research history for v4."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

import duckdb


EXPECTED_MINUTES = 1440
MINIMUM_COMPLETE_SESSION_RATIO = 0.95
MINIMUM_OVERALL_COVERAGE_RATIO = 0.90
MINIMUM_EACH_YEAR_COVERAGE_RATIO = 0.80


def weekdays(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)
            if (start + timedelta(days=offset)).weekday() < 5]


def source_receipt(root: Path) -> dict:
    files = sorted(root.glob("year=*/month=*/data.parquet"))
    if not files:
        raise ValueError("source contains no partitioned parquet files")
    members, digest = [], hashlib.sha256()
    for path in files:
        member = {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        encoded = json.dumps(member, sort_keys=True, separators=(",", ":")).encode()
        digest.update(encoded + b"\n")
        members.append(member)
    return {"root": str(root), "files": len(members),
            "bytes": sum(row["bytes"] for row in members),
            "manifest_sha256": digest.hexdigest(), "members": members}


def observed_sessions(root: Path) -> list[tuple[date, int]]:
    pattern = str(root / "year=*" / "month=*" / "data.parquet")
    return duckdb.connect(":memory:").execute(
        """WITH localized AS (
          SELECT timezone('America/New_York', to_timestamp(ts)) AS local_ts
          FROM read_parquet(?)
        ), sessions AS (
          SELECT CASE WHEN CAST(local_ts AS TIME) >= TIME '17:00:00'
                 THEN CAST(local_ts AS DATE) + 1 ELSE CAST(local_ts AS DATE) END AS session_day,
                 count(DISTINCT date_trunc('minute', local_ts)) AS observed_minutes
          FROM localized GROUP BY 1
        )
        SELECT session_day, observed_minutes FROM sessions
        WHERE dayofweek(session_day) BETWEEN 1 AND 5 ORDER BY session_day""",
        [pattern],
    ).fetchall()


def evaluate(rows: list[tuple[date, int]], receipt: dict) -> dict:
    if not rows:
        raise ValueError("source contains no weekday Forex sessions")
    first, last = rows[0][0], rows[-1][0]
    complete = {day for day, minutes in rows
                if minutes / EXPECTED_MINUTES >= MINIMUM_COMPLETE_SESSION_RATIO}
    by_year = {}
    for year in range(first.year, last.year + 1):
        start, end = max(first, date(year, 1, 1)), min(last, date(year, 12, 31))
        expected = weekdays(start, end)
        count = sum(day in complete for day in expected)
        by_year[str(year)] = {
            "from": start.isoformat(), "to": end.isoformat(),
            "expected_weekdays": len(expected), "complete_sessions": count,
            "coverage_ratio": count / len(expected) if expected else 0.0,
        }
    eligible_start_year = None
    for candidate in range(first.year, last.year + 1):
        if all(by_year[str(year)]["coverage_ratio"] >= MINIMUM_EACH_YEAR_COVERAGE_RATIO
               for year in range(candidate, last.year + 1)):
            eligible_start_year = candidate
            break
    selected_start = max(first, date(eligible_start_year, 1, 1)) if eligible_start_year else None
    expected = weekdays(selected_start, last) if selected_start else []
    complete_count = sum(day in complete for day in expected)
    overall = complete_count / len(expected) if expected else 0.0
    minimum_year = (min(by_year[str(year)]["coverage_ratio"]
                        for year in range(eligible_start_year, last.year + 1))
                    if eligible_start_year else 0.0)
    passed = bool(eligible_start_year is not None
                  and overall >= MINIMUM_OVERALL_COVERAGE_RATIO
                  and minimum_year >= MINIMUM_EACH_YEAR_COVERAGE_RATIO)
    return {
        "schema_version": 1, "symbol": "EURUSD", "timeframe": "D1",
        "performance_accessed": False, "source": receipt,
        "session": {"timezone": "America/New_York", "boundary": "17:00",
                    "expected_minutes": EXPECTED_MINUTES,
                    "minimum_complete_session_ratio": MINIMUM_COMPLETE_SESSION_RATIO},
        "available_observation_span": {"first": first.isoformat(), "last": last.isoformat()},
        "coverage_by_calendar_year": by_year,
        "selection_policy": "longest suffix ending at latest observation with every calendar segment >= 0.80; no performance",
        "selected_research_span": ({"first": selected_start.isoformat(), "last": last.isoformat()}
                                   if selected_start else None),
        "historical_expected_observations": len(expected),
        "historical_complete_observations": complete_count,
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


def audit(root: Path) -> dict:
    return evaluate(observed_sessions(root), source_receipt(root))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "decision", "selected_research_span", "historical_expected_observations",
        "historical_complete_observations", "historical_overall_coverage_ratio",
        "historical_minimum_period_coverage_ratio")}, indent=2))


if __name__ == "__main__":
    main()
