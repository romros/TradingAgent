import pandas as pd

from lab.sq_bridge.btc_multimechanism_v11 import enrich, signals


def test_regime_donchian_requires_matching_completed_regime():
    index = pd.date_range("2020-01-01", periods=260, freq="h", tz="UTC")
    close = pd.Series([100 + i * .5 for i in range(260)], index=index)
    frame = enrich(pd.DataFrame({"open": close, "high": close + .2, "low": close - .2,
                                 "close": close, "complete": True}, index=index))
    params = {"side": "long", "regime_ema": 100, "lookback": 24, "exit_lookback": 12, "stop_atr": 2}
    frame["regime_100"] = -1
    blocked, _ = signals(frame, "regime_donchian", params)
    frame["regime_100"] = 1
    allowed, _ = signals(frame, "regime_donchian", params)
    assert not blocked.any() and allowed.iloc[-1]
