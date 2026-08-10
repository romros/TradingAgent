import unittest
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from screen_xau_macro_regime import build_trades, week_end, weekly_last


class XauMacroScreenTests(unittest.TestCase):
    def test_weekly_last_uses_last_known_observation(self):
        values = {date(2020, 1, 6): 1.0, date(2020, 1, 9): 2.0}
        self.assertEqual(weekly_last(values)[date(2020, 1, 10)], 2.0)

    def test_week_end_maps_weekend_consistently(self):
        self.assertEqual(week_end(date(2020, 1, 6)), date(2020, 1, 10))

    def test_macro_signal_is_lagged_one_week_before_entry(self):
        weeks = [date(2020, 1, 3), date(2020, 1, 10), date(2020, 1, 17), date(2020, 1, 24)]
        gold = dict(zip(weeks, [100.0, 101.0, 103.0, 106.0]))
        real_yield = dict(zip(weeks, [2.0, 1.0, 1.0, 1.0]))
        dollar = dict(zip(weeks, [100.0, 99.0, 99.0, 99.0]))
        trades = build_trades(gold, real_yield, dollar, lookback=1)
        self.assertEqual(trades[0]["factor_date"], date(2020, 1, 10))
        self.assertEqual(trades[0]["date"], date(2020, 1, 17))
        self.assertAlmostEqual(trades[0]["signed_return"], 106 / 103 - 1)


if __name__ == "__main__":
    unittest.main()
