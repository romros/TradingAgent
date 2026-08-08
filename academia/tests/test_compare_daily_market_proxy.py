import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import compare_daily_market_proxy as proxy


class CompareDailyMarketProxyTest(unittest.TestCase):
    def test_compare_reports_overlap_and_return_parity(self):
        source = {"2024-01-01": 100.0, "2024-01-02": 102.0, "2024-01-03": 101.0}
        target = {"2024-01-01": 100.0, "2024-01-02": 102.0, "2024-01-03": 101.0}
        result = proxy.compare(source, target)
        self.assertEqual(result["common_days"], 3)
        self.assertEqual(result["close_absolute_difference_bps_p95"], 0.0)
        self.assertAlmostEqual(result["daily_return_correlation"], 1.0)
        self.assertAlmostEqual(result["daily_return_correlation_by_target_day_lag"]["0"], 1.0)
        self.assertEqual(result["best_target_day_lag"], 0)
        self.assertEqual(result["aligned_close_absolute_difference_bps_p95"], 0.0)

    def test_coinbase_shape_uses_close_and_rejects_duplicates(self):
        rows = [[1704067200, 90, 110, 100, 105, 4]]
        self.assertEqual(proxy.daily_closes(rows), {"2024-01-01": 105.0})
        with self.assertRaises(ValueError):
            proxy.daily_closes(rows + rows)

    def test_summary_does_not_expose_prices(self):
        result = proxy.compare({"2024-01-01": 100}, {"2024-01-01": 101})
        self.assertNotIn("candles", result)
        self.assertNotIn("closes", result)


if __name__ == "__main__":
    unittest.main()
