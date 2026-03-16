from datetime import date, datetime, timezone
from typing import Optional

import yfinance as yf


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
