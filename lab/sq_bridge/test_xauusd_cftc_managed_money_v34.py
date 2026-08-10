from datetime import date

from lab.sq_bridge.xauusd_cftc_managed_money_v34 import non_overlapping, raw_signals


def _row(day, value, available=True):
    return {"report_date": date.fromisoformat(day), "available_at": f"{day}T15:30:00-05:00",
            "available": available, "net_oi_pct": value}


def test_signal_requires_complete_available_window():
    rows = [_row("2023-01-03", 0), _row("2023-01-10", 2, False), _row("2023-01-17", 4)]
    assert raw_signals(rows, 2, 1) == []


def test_symmetric_signals_and_non_overlap():
    rows = [_row("2023-01-03", 0), _row("2023-01-10", 2),
            _row("2023-01-17", -2), _row("2023-01-24", 2)]
    signals = raw_signals(rows, 1, 1)
    assert [row["side"] for row in signals] == [1, -1, 1]
    trades = non_overlapping(signals, 2)
    assert len(trades) == 2
    assert [row["side"] for row in trades] == [1, 1]
