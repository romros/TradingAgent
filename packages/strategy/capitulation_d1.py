import math
from datetime import datetime, timezone
from typing import Optional

from packages.shared.models import SignalRecord


class CapitulationD1Strategy:
    STRATEGY_NAME = "capitulation_d1"

    def __init__(self, body_thresh: float = -0.02, bb_period: int = 20, bb_std: float = 2.0):
        self.body_thresh = body_thresh
        self.bb_period = bb_period
        self.bb_std = bb_std

    def _bb_lower(self, closes: list) -> float:
        n = len(closes)
        mean = sum(closes) / n
        variance = sum((c - mean) ** 2 for c in closes) / n
        std = math.sqrt(variance)
        return mean - self.bb_std * std

    def detect(self, candles: list, asset: str = "", mode: str = "paper") -> Optional[SignalRecord]:
        """
        candles: llista de dicts {date: str, open, high, low, close} ordenats
                 cronològicament (el més recent és l'últim).
        Detecta si l'última candle és un senyal:
          body_pct = (close - open) / open
          Condició: body_pct < body_thresh AND close < BB_lower(period, std)
        Retorna SignalRecord si senyal, None altrament.
        """
        if len(candles) < self.bb_period:
            return None

        last = candles[-1]
        open_price = float(last["open"])
        close_price = float(last["close"])

        if open_price == 0:
            return None

        body_pct = (close_price - open_price) / open_price

        closes = [float(c["close"]) for c in candles[-self.bb_period:]]
        bb_lower = self._bb_lower(closes)

        if body_pct < self.body_thresh and close_price < bb_lower:
            return SignalRecord(
                candle_date=str(last["date"]),
                asset=asset,
                strategy=self.STRATEGY_NAME,
                direction="long",
                body_pct=body_pct,
                bb_lower=bb_lower,
                close_price=close_price,
                mode=mode,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        return None
