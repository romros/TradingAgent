from datetime import date, datetime, timezone, timedelta
from typing import Optional

import yfinance as yf

# Mínim candles esperat (DATA_LOOKBACK_DAYS ~365 → ~252 trading days)
MIN_CANDLES = 200
MAX_GAP_CALENDAR_DAYS = 5  # Gaps > 5 dies (excloent setmana) → warning


def validate_candles(candles: list) -> dict:
    """
    Valida qualitat de candles D1.
    Retorna {status: ok|warning|error, warnings: [], errors: []}
    """
    result = {"status": "ok", "warnings": [], "errors": []}

    if not candles:
        result["status"] = "error"
        result["errors"].append("candles_empty")
        return result

    if len(candles) < MIN_CANDLES:
        result["status"] = "warning" if len(candles) >= 100 else "error"
        result["warnings"].append(f"candles_count={len(candles)} < {MIN_CANDLES}")

    for i, c in enumerate(candles):
        for key in ("open", "high", "low", "close"):
            val = c.get(key)
            if val is None or (isinstance(val, float) and (val != val or val < 0)):
                result["errors"].append(f"candle_{i}_{key}_invalid")
                result["status"] = "error"
        o, h, l, close_val = c.get("open"), c.get("high"), c.get("low"), c.get("close")
        if all(x is not None and x == x for x in (o, h, l, close_val)):
            if h < max(o, close_val) or l > min(o, close_val):
                result["errors"].append(f"candle_{i}_ohlc_inconsistent")
                result["status"] = "error"

    # Timestamps ordenats
    dates = []
    for c in candles:
        d = c.get("date")
        if d:
            try:
                if isinstance(d, str):
                    dates.append(datetime.strptime(d[:10], "%Y-%m-%d").date())
                else:
                    dates.append(d)
            except (ValueError, TypeError):
                result["errors"].append("date_parse_error")
    if len(dates) > 1:
        for i in range(len(dates) - 1):
            gap = (dates[i + 1] - dates[i]).days
            if gap > MAX_GAP_CALENDAR_DAYS:
                result["warnings"].append(f"gap_days={gap} between {dates[i]} and {dates[i+1]}")
                if result["status"] == "ok":
                    result["status"] = "warning"

    if result["errors"]:
        result["status"] = "error"
    elif result["warnings"] and result["status"] == "ok":
        result["status"] = "warning"

    return result


class YFinanceD1Feed:
    def fetch(self, ticker: str, days: int = 365) -> list:
        """
        Retorna llista de dicts {date: 'YYYY-MM-DD', open, high, low, close}
        ordenats cronològicament. Ignora el dia actual si el mercat no ha tancat.
        """
        import pandas as pd

        period = f"{days}d"
        raw = yf.download(ticker, period=period, interval="1d", auto_adjust=True, progress=False)

        if raw is None or raw.empty:
            return []

        # Gestiona MultiIndex si hi és (quan es descarrega un sol ticker pot tenir-lo)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)

        raw = raw.rename(columns=str.lower)

        today = date.today()
        result = []
        for idx, row in raw.iterrows():
            if hasattr(idx, "date"):
                row_date = idx.date()
            else:
                row_date = idx

            # Ignora el dia actual si el mercat pot no haver tancat
            if row_date >= today:
                continue

            result.append({
                "date": row_date.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            })

        return result
