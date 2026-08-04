from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from packages.shared.models import SignalRecord


class MsftCloseDriftStrategy:
    """Long-only close-to-close pullback inside a positive close trend."""

    STRATEGY_NAME = "msft_close_drift_v24"

    def __init__(self, sma_period: int = 100, roc_days: int = 5,
                 pullback_threshold: float = -0.02, holding_days: int = 5):
        self.sma_period = sma_period
        self.roc_days = roc_days
        self.pullback_threshold = pullback_threshold
        self.holding_days = holding_days
        self.minimum_candles = sma_period + 2

    def detect(self, candles: list, asset: str = "MSFT", mode: str = "paper") -> Optional[SignalRecord]:
        """Evaluate D-1 after D has closed; intended entry is D robust close."""
        if asset.upper() != "MSFT" or len(candles) < self.minimum_candles:
            return None
        closes = [float(candle["close"]) for candle in candles]
        pullback_index = len(closes) - 2
        trend_index = pullback_index - 1
        roc_base_index = pullback_index - self.roc_days
        if roc_base_index < 0 or closes[roc_base_index] <= 0:
            return None
        trend_window = closes[trend_index - self.sma_period + 1:trend_index + 1]
        if len(trend_window) != self.sma_period:
            return None
        sma = sum(trend_window) / self.sma_period
        roc = closes[pullback_index] / closes[roc_base_index] - 1
        if closes[trend_index] <= sma or roc > self.pullback_threshold:
            return None
        return SignalRecord(
            candle_date=str(candles[pullback_index]["date"]), asset="MSFT",
            strategy=self.STRATEGY_NAME, direction="long", body_pct=roc,
            bb_lower=sma, close_price=closes[-1], mode=mode,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
