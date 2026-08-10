import json
from pathlib import Path

import pandas as pd
import pytest

from lab.sq_bridge.xauusd_abnormal_day_momentum_v36_train import (
    coverage_gate,
    parameter_grid,
    selected_leverage,
    session_records,
    simulate,
    trades_for,
)


CONFIG = json.loads((Path(__file__).parent /
                     "family_xauusd_abnormal_day_momentum_v36.json").read_text())


def record(day, partial, full, rows):
    frame = pd.DataFrame(rows, columns=("open", "high", "low", "close"),
                         index=pd.date_range(f"{day} 15:00Z", periods=len(rows), freq="15min"))
    return {"session_date": day, "anchor": 100, "partial_return": partial,
            "full_return": full, "entry_time": frame.index[0],
            "exit_time": frame.index[-1] + pd.Timedelta(minutes=15),
            "entry": 100, "exit": float(frame.iloc[-1]["close"]), "path": frame}


def test_grid_is_exactly_the_preregistered_36_points():
    assert len(parameter_grid(CONFIG)) == 36


def test_current_full_return_cannot_leak_into_its_own_signal_threshold():
    quiet = [(100, 100, 100, 100)]
    records = [record("2010-01-01", 0, 0, quiet),
               record("2010-01-02", 0, 0, quiet),
               record("2010-01-03", 0.02, 0.50, [(100, 102, 100, 102)])]
    trades = trades_for(records, lookback=2, deviations=2, stop=.01,
                        economics=CONFIG["economics"])
    assert len(trades) == 1
    assert trades[0]["threshold_mean"] == 0
    assert trades[0]["threshold_sigma"] == 0
    assert trades[0]["side"] == 1


def test_stop_precedes_time_exit_and_leverage_uses_official_buffer():
    falling = record("2010-01-03", .02, 0, [(100, 100.1, 98.5, 99)])
    trade = simulate(falling, side=1, stop=.01, economics=CONFIG["economics"])
    assert selected_leverage(.01, CONFIG["economics"]) == 50
    assert trade["exit_reason"] == "stop"
    assert trade["liquidated"] is False
    assert trade["gross_return"] == pytest.approx(-0.01)
    assert trade["liquidation_fraction"] == pytest.approx(.015)


def test_missing_intraday_minutes_block_before_performance():
    local = ([pd.Timestamp("2010-01-04 18:15", tz="America/New_York"),
              pd.Timestamp("2010-01-05 09:45", tz="America/New_York")]
             + list(pd.date_range("2010-01-05 10:00", "2010-01-05 16:45",
                                  freq="15min", tz="America/New_York")))
    index = pd.DatetimeIndex(local).tz_convert("UTC")
    frame = pd.DataFrame({"open": 100, "high": 101, "low": 99, "close": 100,
                          "minute_count": 15}, index=index)
    complete = session_records(frame, "10:00")
    assert len(complete) == 1
    assert coverage_gate(frame, {"10:00": complete})["pass"] is True
    frame.loc[pd.Timestamp("2010-01-05 12:00", tz="America/New_York").tz_convert("UTC"),
              "minute_count"] = 14
    incomplete = session_records(frame, "10:00")
    result = coverage_gate(frame, {"10:00": incomplete})
    assert len(incomplete) == 0
    assert result["pass"] is False
