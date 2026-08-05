from datetime import datetime, timezone

from lab.sq_bridge.ostium_fx_quarantine import (
    detect_roll_window_anomalies, exclude_quarantined_dates, quarantined_local_dates,
)
from lab.sq_bridge.ostium_fx_quarantine_audit import load_input


def _row(iso, close):
    return {"ts": int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()),
            "open": close, "high": close, "low": close, "close": close, "volume": 0}


def test_flags_large_contiguous_jump_in_new_york_roll_window():
    # July is EDT: 17:00 New York is 21:00 UTC.
    rows = [_row("2026-07-03T20:57:00", 1.20), _row("2026-07-03T20:58:00", 1.18)]
    receipts = detect_roll_window_anomalies(rows)
    assert len(receipts) == 1
    assert receipts[0]["local_date"] == "2026-07-03"
    assert receipts[0]["reason"] == "NY_ROLL_WINDOW_CLOSE_JUMP"


def test_ignores_same_jump_outside_window_and_small_jump_inside_it():
    rows = [
        _row("2026-07-03T18:00:00", 1.20), _row("2026-07-03T18:01:00", 1.18),
        _row("2026-07-03T20:59:00", 1.20), _row("2026-07-03T21:00:00", 1.2005),
    ]
    assert detect_roll_window_anomalies(rows) == []


def test_excludes_whole_local_date_and_keeps_receipt_dates_deduplicated():
    rows = [_row("2026-07-03T20:57:00", 1.20), _row("2026-07-03T20:58:00", 1.18),
            _row("2026-07-06T14:00:00", 1.21)]
    dates = quarantined_local_dates(detect_roll_window_anomalies(rows))
    kept = exclude_quarantined_dates(rows, dates)
    assert dates == {"2026-07-03"}
    assert kept == [rows[-1]]


def test_non_contiguous_rows_do_not_create_false_jump():
    rows = [_row("2026-07-03T20:57:00", 1.20), _row("2026-07-03T20:59:00", 1.18)]
    assert detect_roll_window_anomalies(rows) == []


def test_audit_loader_reads_headerless_recorder_csv(tmp_path):
    source = tmp_path / "02.csv"
    source.write_text("60,1.0,1.2,0.9,1.1,0.0\n")
    assert load_input(source) == [
        {"ts": 60, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 0.0}
    ]
