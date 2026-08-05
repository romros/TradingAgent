import pytest

from datetime import datetime, timezone

from lab.sq_bridge.canonical_ohlcv import (
    aggregate_fx_daily_ny_close, aggregate_m1, complete_by_timestamp,
)


def _row(ts, open_, high, low, close, volume=1):
    return {"ts": ts, "open": open_, "high": high, "low": low,
            "close": close, "volume": volume}


def test_aggregates_exact_ohlcv_and_completeness():
    rows = [
        _row(0, 100, 102, 99, 101, 2),
        _row(60, 101, 104, 100, 103, 3),
        _row(120, 103, 105, 98, 99, 5),
        _row(180, 99, 101, 97, 100, 7),
        _row(240, 100, 106, 100, 105, 11),
    ]
    bar = aggregate_m1(rows, 5)[0]
    assert (bar.ts, bar.open, bar.high, bar.low, bar.close) == (0, 100, 106, 97, 105)
    assert bar.volume == 28
    assert bar.complete is True


def test_incomplete_bucket_is_visible_but_excluded_by_complete_map():
    bars = aggregate_m1([_row(0, 1, 1, 1, 1), _row(120, 1, 1, 1, 1)], 5)
    assert bars[0].observed_minutes == 2
    assert complete_by_timestamp(bars) == {}


def test_origin_offset_controls_bucket_boundaries():
    rows = [_row(60, 1, 1, 1, 1), _row(120, 1, 1, 1, 1)]
    bars = aggregate_m1(rows, 5, origin_offset_minutes=1)
    assert bars[0].ts == 60


@pytest.mark.parametrize("rows,reason", [
    ([_row(1, 1, 1, 1, 1)], "NON_MINUTE_TIMESTAMP"),
    ([_row(0, 1, 1, 1, 1), _row(0, 1, 1, 1, 1)], "DUPLICATE_TIMESTAMP"),
    ([_row(0, 1, .9, 1, 1)], "INVALID_OHLC"),
])
def test_invalid_input_fails_closed(rows, reason):
    with pytest.raises(ValueError, match=reason):
        aggregate_m1(rows, 5)


def test_daily_forex_session_uses_new_york_close_and_dst():
    def at(iso):
        return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())

    # 2026-03-08 is the US spring DST transition. The trading session labelled
    # Monday starts Sunday 17:00 NY (21:00 UTC after the transition).
    rows = [
        _row(at("2026-03-08T21:00:00"), 1, 1, 1, 1),
        _row(at("2026-03-09T20:59:00"), 1, 1, 1, 1),
    ]
    bar = aggregate_fx_daily_ny_close(rows)[0]
    assert bar.ts == at("2026-03-08T21:00:00")
    assert bar.expected_minutes == 1440
    assert bar.observed_minutes == 2


def test_daily_expected_minutes_reflect_dst_crossing():
    def at(iso):
        return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())

    # Before DST, 17:00 NY is 22:00 UTC; after DST the previous test proves
    # that it is 21:00 UTC. The market is closed during the Sunday transition,
    # so each actual Forex trading session still expects 1,440 minutes.
    before_dst = aggregate_fx_daily_ny_close([
        _row(at("2026-03-01T22:00:00"), 1, 1, 1, 1)
    ])[0]
    assert before_dst.ts == at("2026-03-01T22:00:00")
    assert before_dst.expected_minutes == 1440
