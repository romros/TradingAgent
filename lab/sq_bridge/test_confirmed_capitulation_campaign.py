import unittest

import numpy as np
import pandas as pd

from lab.sq_bridge.confirmed_capitulation_campaign import metrics, trades


class ConfirmedCapitulationCampaignTest(unittest.TestCase):
    def test_no_signal_has_stable_empty_schema(self):
        index = pd.bdate_range("2010-01-01", periods=260)
        close = pd.Series(np.linspace(100, 130, len(index)), index=index)
        frame = pd.DataFrame({"open": close, "high": close * 1.001,
                              "low": close * .999, "close": close})
        result = trades(frame, (2.5, .5, 2, True))
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns),
                         ["entry_date", "exit_date", "entry_i", "hold", "gross_return", "mae"])

    def test_confirmation_enters_after_recovery_not_on_crash(self):
        index = pd.bdate_range("2010-01-01", periods=230)
        close = pd.Series(100 + np.sin(np.arange(len(index))) * .1, index=index)
        close.iloc[220] = 90.0
        close.iloc[221] = 96.0
        close.iloc[222:] = 97.0
        frame = pd.DataFrame({"open": close, "high": close * 1.01,
                              "low": close * .99, "close": close})
        result = trades(frame, (1.5, .5, 1, False))
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0].entry_date, index[221])
        self.assertEqual(result.iloc[0].exit_date, index[222])

    def test_metrics_compound_trade_returns(self):
        values = pd.Series([.10, -.05])
        dates = pd.Series(pd.to_datetime(["2020-01-02", "2020-02-03"]))
        result = metrics(values, dates)
        self.assertAlmostEqual(result["total_pct"], 4.5)
        self.assertAlmostEqual(result["profit_factor"], 2.0)


if __name__ == "__main__":
    unittest.main()
