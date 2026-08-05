import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import probe_ostium_ohlc


class ProbeOstiumOhlcTest(unittest.TestCase):
    def test_summary_exposes_coverage_without_candles(self):
        payload = {"data": [
            {"time": 1704067200000, "open": 1, "high": 2, "low": 1, "close": 2},
            {"time": 1785456000000, "open": 2, "high": 3, "low": 2, "close": 3},
        ]}
        result = probe_ostium_ohlc.summarize(payload, "2017-01-01", "2026-07-31")
        self.assertEqual(result["first"], "2024-01-01")
        self.assertEqual(result["last"], "2026-07-31")
        self.assertFalse(result["covers_requested_start"])
        self.assertTrue(result["covers_requested_end"])
        self.assertNotIn("data", result)

    def test_empty_history_fails_both_coverage_edges(self):
        result = probe_ostium_ohlc.summarize({"data": []}, "2017-01-01", "2026-07-31")
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["covers_requested_start"])
        self.assertFalse(result["covers_requested_end"])

    def test_internal_market_identifiers_are_explicit(self):
        self.assertEqual(probe_ostium_ohlc.DEFAULT_ASSETS["US500/USD"], "SPX-USD")
        self.assertEqual(probe_ostium_ohlc.DEFAULT_ASSETS["WTI/USD"], "CL-USD")


if __name__ == "__main__":
    unittest.main()
