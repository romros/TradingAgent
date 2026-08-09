import unittest

import pandas as pd

from spx_turn_of_month_v4 import build_trades, metrics


class SpxTurnOfMonthTest(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({
            "day": pd.to_datetime([
                "2017-01-27", "2017-01-30", "2017-01-31",
                "2017-02-01", "2017-02-02", "2017-02-03",
                "2017-02-27", "2017-02-28", "2017-03-01",
            ]),
            "close_1559": [100, 101, 102, 103, 104, 105, 106, 107, 108],
        })

    def test_month_offsets_use_trading_rows(self):
        trades = build_trades(self.frame(), entry_from_month_end=0, exit_day_next_month=2)
        self.assertEqual(trades[0]["entry_day"], "2017-01-31")
        self.assertEqual(trades[0]["exit_day"], "2017-02-02")
        self.assertAlmostEqual(trades[0]["gross_return"], 104 / 102 - 1)

    def test_costs_reduce_metrics(self):
        trades = build_trades(self.frame(), entry_from_month_end=0, exit_day_next_month=1)
        self.assertLess(metrics(trades, 30)["mean_net_bps"], metrics(trades, 8)["mean_net_bps"])


if __name__ == "__main__":
    unittest.main()
