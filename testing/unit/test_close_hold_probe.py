import sqlite3
from pathlib import Path

from packages.runtime.close_hold_probe import CloseHoldPaperProbe, CloseHoldProbeConfig
from packages.strategy.msft_close_drift import MsftCloseDriftStrategy


def candles(prices, lows=None):
    lows = lows or prices
    return [{"date": f"2026-01-{i + 1:02d}", "open": price, "high": price,
             "low": lows[i], "close": price} for i, price in enumerate(prices)]


def probe(tmp_path: Path, **overrides):
    strategy = MsftCloseDriftStrategy(sma_period=5, roc_days=2,
                                      pullback_threshold=-.02, holding_days=5)
    values = {"db_path": str(tmp_path / "drift.db"), "capital_initial": 200,
              "leverage": 4, "risk_per_trade_pct": .01,
              "sizing_adverse_move_pct": .1906644080557125,
              "fee_roundtrip_bps": 36}
    values.update(overrides)
    return CloseHoldPaperProbe(strategy, CloseHoldProbeConfig(**values))


def signal_prices():
    return [90, 95, 100, 105, 110, 100, 101]


def test_warming_up_never_opens_trade(tmp_path):
    result = probe(tmp_path).run(candles([100] * 6))
    assert result["status"] == "WARMING_UP"
    with sqlite3.connect(tmp_path / "drift.db") as conn:
        assert conn.execute("SELECT count(*) FROM trades").fetchone()[0] == 0


def test_opens_at_latest_close_with_risk_limited_size_and_is_idempotent(tmp_path):
    engine = probe(tmp_path); data = candles(signal_prices())
    first = engine.run(data); second = engine.run(data)
    assert first["opened"]["entry_price"] == 101
    assert first["opened"]["leverage"] == 4
    assert round(first["opened"]["nominal"], 2) == 10.49
    assert second["reason"] == "SESSION_ALREADY_PROCESSED"
    with sqlite3.connect(tmp_path / "drift.db") as conn:
        assert conn.execute("SELECT count(*) FROM trades").fetchone()[0] == 1


def test_settles_exactly_after_five_new_sessions_and_compounds(tmp_path):
    engine = probe(tmp_path); initial = candles(signal_prices())
    engine.run(initial)
    extended = initial + candles([102, 103, 104, 105, 106])[0:0]
    # Append with unique, ordered dates after the entry session.
    extended = initial + [{"date": f"2026-01-{day:02d}", "open": price, "high": price,
                           "low": price, "close": price}
                          for day, price in zip(range(8, 13), [102, 103, 104, 105, 106])]
    result = engine.run(extended)
    assert result["settled"] is not None
    assert result["settled"]["exit_date"] == "2026-01-12"
    assert result["capital"] > 200


def test_liquidation_is_recorded_from_post_entry_native_lows(tmp_path):
    engine = probe(tmp_path); initial = candles(signal_prices()); engine.run(initial)
    future = [{"date": f"2026-01-{day:02d}", "open": 100, "high": 100,
               "low": 70 if day == 9 else 95, "close": 100}
              for day in range(8, 13)]
    result = engine.run(initial + future)
    assert result["settled"]["status"] == "liq_settled"
    assert result["settled"]["adverse_move"] > .25
    assert result["capital"] < 200
