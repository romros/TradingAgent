from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lab.sq_bridge.spx_d1_source_parity_v4 import aggregate_regular_session, compare


NY = ZoneInfo("America/New_York")


def session(day: int, *, multiplier: float = 1.0, minutes: int = 390) -> list[dict]:
    start = datetime(2026, 1, day, 9, 30, tzinfo=NY)
    rows = []
    for minute in range(minutes):
        local = start + timedelta(minutes=minute)
        base = (6_000 + day * 7 + minute / 100) * multiplier
        rows.append({"ts": int(local.timestamp()), "open": base, "high": base + .5,
                     "low": base - .5, "close": base + .1, "volume": 1})
    return rows


def test_regular_session_excludes_incomplete_days():
    rows = session(5) + session(6, minutes=300)
    complete, coverage = aggregate_regular_session(rows)
    assert set(complete) == {"2026-01-05"}
    assert coverage["2026-01-05"] == 1
    assert coverage["2026-01-06"] < .95


def test_identical_sixty_session_mapping_passes_without_performance():
    rows = []
    day = datetime(2026, 1, 1)
    while len({datetime.fromtimestamp(row["ts"], NY).date() for row in rows}) < 60:
        if day.weekday() < 5:
            rows.extend(session(day.day) if day.month == 1 else _dated_session(day))
        day += timedelta(days=1)
    result = compare(rows, [dict(row) for row in rows])
    assert result["decision"] == "PASS_D1_SOURCE_MAPPING"
    assert result["aligned_complete_sessions"] == 60
    assert result["d1_close_return_correlation"] == 1
    assert result["performance_accessed"] is False


def _dated_session(day: datetime) -> list[dict]:
    start = day.replace(hour=9, minute=30, tzinfo=NY)
    rows = []
    ordinal = day.toordinal()
    for minute in range(390):
        base = 6_000 + ordinal % 101 + minute / 100
        local = start + timedelta(minutes=minute)
        rows.append({"ts": int(local.timestamp()), "open": base, "high": base + .5,
                     "low": base - .5, "close": base + .1, "volume": 1})
    return rows


def test_sparse_or_divergent_mapping_blocks():
    reference = session(5)
    ostium = session(5, multiplier=1.2)
    result = compare(reference, ostium)
    assert result["decision"] == "BLOCK_D1_SOURCE_MAPPING"
    assert "ALIGNED_COMPLETE_SESSIONS_LT_60" in result["reasons"]


def test_non_overlapping_complete_tails_do_not_reduce_common_span_coverage():
    reference = _dated_session(datetime(2026, 1, 5)) + _dated_session(datetime(2026, 1, 6))
    ostium = (_dated_session(datetime(2026, 1, 2))
              + _dated_session(datetime(2026, 1, 5))
              + _dated_session(datetime(2026, 1, 6))
              + _dated_session(datetime(2026, 1, 7)))
    result = compare(reference, ostium)
    assert result["common_observed_span"] == {"first": "2026-01-05", "last": "2026-01-06"}
    assert result["common_complete_session_coverage_ratio"] == 1
