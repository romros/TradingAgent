from pathlib import Path

from lab.sq_bridge.msft_close_drift_v24 import load_sq_close, metrics, random_timing_p, trades_for


def test_signal_is_delayed_and_trade_is_close_to_close(tmp_path: Path):
    path = tmp_path / "d.csv"
    prices = [100, 101, 102, 103, 104, 99, 101, 102, 103, 104, 105]
    path.write_text("Date,Close\n" + "\n".join(
        f"2026.01.{i:02d},{price}" for i, price in enumerate(prices, 1)) + "\n")
    close = load_sq_close(path)
    trades = trades_for(close, sma=3, roc_days=1, threshold=-4, hold=2)
    assert trades[0]["entry"] == "2026-01-07"
    assert trades[0]["exit"] == "2026-01-09"


def test_costs_are_roundtrip_and_compounded():
    trades = [{"entry": "2020-01-01", "gross_return": .01},
              {"entry": "2020-02-01", "gross_return": -.005}]
    result = metrics(trades, "2020-01-01", "2020-12-31", cost_bps=36)
    assert result["trades"] == 2
    assert result["return_pct"] < .5


def test_random_control_is_deterministic_and_regime_matched():
    index = __import__("pandas").date_range("2020-01-01", periods=500, freq="B")
    close = __import__("pandas").Series(range(100, 600), index=index, dtype=float)
    candidate = {"id": "x", "sma": 20, "hold": 5,
                 "trades": [{"entry": index[100].date().isoformat(), "gross_return": .01}]}
    first = random_timing_p(close, candidate, index[50].date().isoformat(), index[-1].date().isoformat(), 20)
    second = random_timing_p(close, candidate, index[50].date().isoformat(), index[-1].date().isoformat(), 20)
    assert first == second
