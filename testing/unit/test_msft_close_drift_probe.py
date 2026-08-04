from datetime import datetime, timezone

import pytest

from packages.market.ostium_clean_d1 import aggregate_complete_regular_sessions
from packages.strategy.msft_close_drift import MsftCloseDriftStrategy
from packages.runtime.msft_close_drift_runner import run_msft_close_drift_probe


def _candles(prices):
    return [{"date": f"2026-01-{index + 1:02d}", "close": price,
             "open": price, "high": price, "low": price} for index, price in enumerate(prices)]


def test_strategy_waits_for_warmup_and_uses_previous_closed_day():
    strategy = MsftCloseDriftStrategy(sma_period=5, roc_days=2, pullback_threshold=-.02)
    assert strategy.detect(_candles([100] * 6), "MSFT") is None
    signal = strategy.detect(_candles([90, 95, 100, 105, 110, 100, 101]), "MSFT")
    assert signal is not None
    assert signal.candle_date == "2026-01-06"
    assert signal.close_price == 101
    assert signal.strategy == "msft_close_drift_v24"


def test_strategy_rejects_other_assets():
    strategy = MsftCloseDriftStrategy(sma_period=3, roc_days=1)
    assert strategy.detect(_candles([100, 101, 98, 99, 100]), "NVDA") is None


def test_regular_session_aggregation_requires_complete_clean_day():
    start = int(datetime(2026, 7, 1, 13, 30, tzinfo=timezone.utc).timestamp())
    rows = [[start + minute * 60, 100, 101, 99, 100 + minute / 1000, 0]
            for minute in range(390)]
    daily = aggregate_complete_regular_sessions(rows)
    assert len(daily) == 1
    assert daily[0]["bars"] == 390
    assert daily[0]["source"] == "ostium_clean"


def test_regular_session_aggregation_fails_closed_on_outlier():
    start = int(datetime(2026, 7, 1, 13, 30, tzinfo=timezone.utc).timestamp())
    rows = [[start, 100, 100, 100, 100, 0], [start + 60, 120, 120, 120, 120, 0]]
    with pytest.raises(ValueError, match="OUTLIER"):
        aggregate_complete_regular_sessions(rows, minimum_bars=1)


def test_runner_blocks_non_executable_close_fill(monkeypatch):
    monkeypatch.delenv("MSFT_DRIFT_EXECUTION_COMPATIBLE", raising=False)
    result = run_msft_close_drift_probe()
    assert result["status"] == "BLOCKED_EXECUTION_WINDOW"
    assert "15_45" in result["reason"]
