import datetime as dt
import math

from lab.sq_bridge.etf_twelve_one_momentum_screen_v1 import monthly_returns, one_sleeve_metrics
from lab.sq_bridge.etf_relative_momentum_screen_v1 import reviews


def _frames(days, closes, opens=None):
    opens = closes if opens is None else opens
    return {"A": {day: (opens[index], closes[index])
                  for index, day in enumerate(days)},
            "B": {day: (100.0, 100.0) for day in days}}


def test_twelve_one_uses_skipped_month_and_next_open_execution():
    start = dt.date(2020, 1, 1)
    days = [start + dt.timedelta(days=index) for index in range(420)]
    closes = [100.0] * len(days)
    opens = [100.0] * len(days)
    points = reviews(days)
    signal_position = next(position for position, index in enumerate(points[:-1])
                           if index >= 252)
    signal = points[signal_position]
    next_signal = points[signal_position + 1]
    # At the first eligible month end A has positive 12-1 momentum.
    closes[signal - 252] = 100.0
    closes[signal - 21] = 120.0
    # Entry/exit opens, rather than signal closes, determine the return.
    opens[signal + 1] = 100.0
    opens[next_signal + 1] = 110.0
    rows = monthly_returns(_frames(days, closes, opens),
                           dt.date(2020, 1, 1), dt.date(2021, 12, 31))
    assert rows
    target = next(row for row in rows if row["entry"] == days[signal + 1])
    assert target["selected"] == ["A"]
    assert math.isclose(target["return"], 0.10)


def test_twelve_one_holds_cash_when_all_scores_nonpositive():
    start = dt.date(2020, 1, 1)
    days = [start + dt.timedelta(days=index) for index in range(420)]
    frames = {name: {day: (100.0, 100.0) for day in days}
              for name in ("A", "B")}
    rows = monthly_returns(frames, dt.date(2020, 1, 1),
                           dt.date(2021, 12, 31))
    assert rows
    assert all(row["selected"] == [] and row["return"] == 0.0
               for row in rows)
    assert one_sleeve_metrics(rows)["cash_months"] == len(rows)
