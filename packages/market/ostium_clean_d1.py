from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import median
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def aggregate_complete_regular_sessions(rows: list[list], minimum_bars: int = 300) -> list[dict]:
    """Aggregate verified M1 arrays to robust US regular-session D1 closes."""
    by_day = defaultdict(list); seen = set(); previous = None
    for raw in sorted(rows, key=lambda item: int(item[0])):
        ts = int(raw[0]); values = [float(value) for value in raw[1:5]]
        if ts in seen:
            raise ValueError("OSTIUM_DUPLICATE_TIMESTAMP")
        seen.add(ts)
        open_, high, low, close = values
        if min(values) <= 0 or high < max(open_, close) or low > min(open_, close):
            raise ValueError("OSTIUM_INVALID_OHLC")
        if previous and ts - previous[0] == 60 and abs(close / previous[1] - 1) > .05:
            raise ValueError("OSTIUM_CONTIGUOUS_M1_OUTLIER")
        previous = (ts, close)
        local = datetime.fromtimestamp(ts, timezone.utc).astimezone(NY)
        if local.weekday() < 5 and time(9, 30) <= local.time() < time(16, 0):
            by_day[local.date().isoformat()].append((ts, open_, high, low, close))
    result = []
    for day, bars in sorted(by_day.items()):
        if len(bars) < minimum_bars:
            continue
        result.append({"date": day, "open": bars[0][1],
                       "high": max(row[2] for row in bars),
                       "low": min(row[3] for row in bars),
                       "close": median(row[4] for row in bars[-5:]),
                       "bars": len(bars), "source": "ostium_clean"})
    return result


class OstiumCleanD1Feed:
    """BS clean Parquet history plus strictly validated current raw session."""

    def __init__(self, base_url: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/"); self.timeout_s = timeout_s

    def _fetch_pages(self, symbol: str, source: str, start_ts: int, end_ts: int) -> list[list]:
        rows = []; offset = 0
        while True:
            query = urlencode({"source": source, "from_ts": start_ts, "to_ts": end_ts,
                               "limit": 5000, "offset": offset})
            with urlopen(f"{self.base_url}/data/ohlcv/{symbol}?{query}", timeout=self.timeout_s) as response:
                import json
                body = json.loads(response.read())
            page = body.get("candles", []); rows.extend(page)
            next_offset = body.get("next_offset")
            if next_offset is None or not page:
                return rows
            offset = int(next_offset)

    def fetch(self, ticker: str, days: int = 450) -> list[dict]:
        if ticker.upper() != "MSFT":
            return []
        now = datetime.now(timezone.utc); start = now - timedelta(days=days)
        clean = self._fetch_pages("MSFT", "ostium_clean", int(start.timestamp()), int(now.timestamp()))
        today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
        current = self._fetch_pages("MSFT", "ostium", int(today_start.timestamp()), int(now.timestamp()))
        merged = {int(row[0]): row for row in clean}
        for row in current:
            merged[int(row[0])] = row
        return aggregate_complete_regular_sessions(list(merged.values()))
