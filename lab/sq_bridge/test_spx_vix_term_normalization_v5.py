import unittest

import pandas as pd

from spx_vix_term_normalization_v5 import build_trades, metrics


class SpxVixTermNormalizationTest(unittest.TestCase):
    def test_next_session_entry_and_non_overlap(self):
        spx = pd.DataFrame({
            "day": pd.to_datetime(["2017-01-02", "2017-01-03", "2017-01-04", "2017-01-05", "2017-01-06"]),
            "close_1545": [100, 101, 102, 103, 104],
        })
        signals = pd.DataFrame({"DATE": pd.to_datetime(["2017-01-02", "2017-01-03"])})
        trades = build_trades(spx, signals, holding_sessions=2)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["entry_day"], "2017-01-03")
        self.assertEqual(trades[0]["exit_day"], "2017-01-05")
        self.assertAlmostEqual(trades[0]["gross_return"], 103 / 101 - 1)

    def test_costs_reduce_expectancy(self):
        trades = [{"year": 2017, "gross_return": .01, "holding_calendar_days": 2}]
        self.assertLess(metrics(trades, 30)["mean_net_bps"], metrics(trades, 8)["mean_net_bps"])


if __name__ == "__main__":
    unittest.main()
