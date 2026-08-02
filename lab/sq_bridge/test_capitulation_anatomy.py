import unittest

import numpy as np
import pandas as pd

from lab.sq_bridge.capitulation_anatomy import (
    STOP_DISTANCE, event_table, leverage_audit, simulate_portfolio_glidepath, trade_metrics,
)


class CapitulationAnatomyTest(unittest.TestCase):
    def test_frozen_signal_enters_next_open_and_exits_same_close(self):
        index = pd.bdate_range("2020-01-01", periods=230)
        close = pd.Series(100 + np.sin(np.arange(230)) * .1, index=index)
        open_ = close.copy()
        open_.iloc[220], close.iloc[220] = 100.0, 90.0
        open_.iloc[221], close.iloc[221] = 91.0, 95.0
        frame = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.01,
                              "low": np.minimum(open_, close) * .99, "close": close})
        result = event_table(frame)
        event = result[result.signal_date == index[220]].iloc[0]
        self.assertEqual(event.entry_date, index[221])
        self.assertAlmostEqual(event.return_1d, 95 / 91 - 1)

    def test_cost_is_deducted_once(self):
        result = trade_metrics(pd.Series([.01, -.005]), 15)
        self.assertAlmostEqual(result["expectancy_bps"], 10.0)
        self.assertAlmostEqual(result["profit_factor"], .0085 / .0065)

    def test_leverage_uses_adverse_mae_tail(self):
        events = pd.DataFrame({"entry_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
                               "mae_1d": [-.01, -.08]})
        result = leverage_audit(events)
        self.assertAlmostEqual(result["buffered_mae_pct"], 10.0)
        self.assertEqual(result["maximum_grid_leverage_below_buffered_barrier"], 8)
        self.assertGreater(result["diagnostic_stop_distance_pct"], 9.0)

    def test_configured_stops_are_below_liquidation_caps(self):
        caps = {"MSFT": 10, "NVDA": 5, "QQQ": 5}
        for asset, stop in STOP_DISTANCE.items():
            self.assertLess(stop, 1 / caps[asset])

    def test_glidepath_simulation_compounds_both_assets(self):
        index = pd.bdate_range("2003-01-01", periods=240)
        frames = {}
        for asset in ("MSFT", "NVDA"):
            close = pd.Series(100 + np.sin(np.arange(240)) * .1, index=index)
            open_ = close.copy()
            open_.iloc[220], close.iloc[220] = 100, 90
            open_.iloc[221], close.iloc[221] = 91, 95
            frames[asset] = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.01,
                                          "low": np.minimum(open_, close) * .99, "close": close})
        result = simulate_portfolio_glidepath(frames)
        self.assertEqual(result["trades"], 2)
        self.assertGreater(result["scenarios"]["conservative"]["final_usdc"], 200)


if __name__ == "__main__":
    unittest.main()
