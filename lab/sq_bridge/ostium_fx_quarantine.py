"""Fail-closed, source-internal quarantine for Ostium Forex M1 candles.

The detector deliberately uses no reference-market prices.  It identifies
large discontinuities in the New York daily-roll window and returns immutable
receipts; callers decide whether to exclude an entire local date.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


def detect_roll_window_anomalies(
    rows: list[dict], *, threshold_bps: float = 8.0,
    window_start: time = time(16, 55), window_end: time = time(17, 35),
) -> list[dict]:
    if threshold_bps <= 0:
        raise ValueError("threshold_bps must be positive")
    ny = ZoneInfo("America/New_York")
    ordered = sorted(rows, key=lambda row: int(row["ts"]))
    receipts = []
    previous = None
    for row in ordered:
        ts, close = int(row["ts"]), float(row["close"])
        if close <= 0:
            raise ValueError(f"INVALID_CLOSE:{ts}")
        if previous is not None and ts - previous[0] == 60:
            local = datetime.fromtimestamp(ts, timezone.utc).astimezone(ny)
            jump_bps = abs(close / previous[1] - 1) * 10_000
            if window_start <= local.time().replace(tzinfo=None) <= window_end and jump_bps > threshold_bps:
                receipts.append({
                    "reason": "NY_ROLL_WINDOW_CLOSE_JUMP",
                    "local_date": local.date().isoformat(),
                    "timestamp_utc": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                    "timestamp_new_york": local.isoformat(),
                    "jump_bps": jump_bps,
                    "threshold_bps": threshold_bps,
                })
        previous = (ts, close)
    return receipts


def quarantined_local_dates(receipts: list[dict]) -> set[str]:
    return {str(receipt["local_date"]) for receipt in receipts}


def exclude_quarantined_dates(rows: list[dict], dates: set[str]) -> list[dict]:
    ny = ZoneInfo("America/New_York")
    return [
        row for row in rows
        if datetime.fromtimestamp(int(row["ts"]), timezone.utc).astimezone(ny).date().isoformat()
        not in dates
    ]
