"""Deterministic M1 -> OHLCV aggregation used by Alquimia parity and research."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    observed_minutes: int
    expected_minutes: int

    @property
    def complete(self) -> bool:
        return self.observed_minutes == self.expected_minutes


def aggregate_m1(
    rows: list[dict], timeframe_minutes: int, *, origin_offset_minutes: int = 0
) -> list[Bar]:
    """Aggregate closed M1 bars into fixed UTC buckets.

    Duplicate timestamps, non-minute timestamps and invalid OHLC fail closed.
    Empty buckets are not synthesized. Callers decide whether incomplete bars
    can be inspected; parity/research should normally retain only ``complete``.
    """
    if timeframe_minutes < 1:
        raise ValueError("timeframe_minutes must be positive")
    bucket_seconds = timeframe_minutes * 60
    offset_seconds = origin_offset_minutes * 60
    seen = set()
    buckets: dict[int, list[dict]] = {}
    for raw in sorted(rows, key=lambda row: int(row["ts"])):
        ts = int(raw["ts"])
        if ts % 60:
            raise ValueError(f"NON_MINUTE_TIMESTAMP:{ts}")
        if ts in seen:
            raise ValueError(f"DUPLICATE_TIMESTAMP:{ts}")
        seen.add(ts)
        open_, high, low, close = (float(raw[name]) for name in ("open", "high", "low", "close"))
        if min(open_, high, low, close) <= 0 or high < max(open_, close) or low > min(open_, close):
            raise ValueError(f"INVALID_OHLC:{ts}")
        bucket = ((ts - offset_seconds) // bucket_seconds) * bucket_seconds + offset_seconds
        buckets.setdefault(bucket, []).append({
            "ts": ts, "open": open_, "high": high, "low": low, "close": close,
            "volume": float(raw.get("volume", 0) or 0),
        })
    result = []
    for timestamp, bars in sorted(buckets.items()):
        result.append(Bar(
            ts=timestamp,
            open=bars[0]["open"],
            high=max(bar["high"] for bar in bars),
            low=min(bar["low"] for bar in bars),
            close=bars[-1]["close"],
            volume=sum(bar["volume"] for bar in bars),
            observed_minutes=len(bars),
            expected_minutes=timeframe_minutes,
        ))
    return result


def complete_by_timestamp(bars: list[Bar], minimum_coverage: float = 1.0) -> dict[int, Bar]:
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be in (0, 1]")
    return {
        bar.ts: bar for bar in bars
        if bar.observed_minutes / bar.expected_minutes >= minimum_coverage
    }


def aggregate_fx_daily_ny_close(
    rows: list[dict], *, close_hour: int = 17, minimum_weekday: bool = True
) -> list[Bar]:
    """Aggregate M1 into Forex trading days ending at New York close.

    Session labels and expected minutes are DST-aware. A normal session has
    1,440 minutes; the sessions crossing US DST have 1,380 or 1,500. Weekend
    labels are excluded, while Monday correctly starts Sunday at 17:00 NY.
    """
    ny = ZoneInfo("America/New_York")
    grouped: dict[date, list[dict]] = {}
    validated = aggregate_m1(rows, 1)
    canonical = {bar.ts: bar for bar in validated}
    for ts, bar in sorted(canonical.items()):
        local = datetime.fromtimestamp(ts, timezone.utc).astimezone(ny)
        label = local.date() + timedelta(days=1) if local.time() >= time(close_hour) else local.date()
        if minimum_weekday and label.weekday() >= 5:
            continue
        grouped.setdefault(label, []).append({
            "ts": ts, "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
        })
    result = []
    for label, bars in sorted(grouped.items()):
        end_local = datetime.combine(label, time(close_hour), tzinfo=ny)
        start_local = datetime.combine(label - timedelta(days=1), time(close_hour), tzinfo=ny)
        expected = int((end_local.timestamp() - start_local.timestamp()) // 60)
        result.append(Bar(
            ts=int(start_local.timestamp()),
            open=bars[0]["open"], high=max(bar["high"] for bar in bars),
            low=min(bar["low"] for bar in bars), close=bars[-1]["close"],
            volume=sum(bar["volume"] for bar in bars),
            observed_minutes=len(bars), expected_minutes=expected,
        ))
    return result
