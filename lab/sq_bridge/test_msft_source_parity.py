import unittest
from datetime import datetime, timezone

from msft_source_parity import aggregate_regular_session, compare


class MsftSourceParityTest(unittest.TestCase):
    def test_aggregation_uses_new_york_regular_session_and_flags_jump(self):
        rows = []
        for minute, price in enumerate((100.0, 100.1, 100.2, 80.0, 100.3, 100.4, 100.5)):
            dt = datetime(2026, 7, 1, 14, minute, tzinfo=timezone.utc)
            rows.append({"ts": int(dt.timestamp()), "dt_utc": dt,
                         "dt_ny": dt.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')),
                         "open": price, "high": price, "low": price, "close": price})
        daily, anomalies = aggregate_regular_session(rows)
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["close"], 100.3)
        self.assertEqual(len(anomalies), 1)

    def test_exact_comparison(self):
        rows = [{"date": "2026-01-01", "close": 100.0},
                {"date": "2026-01-02", "close": 101.0},
                {"date": "2026-01-03", "close": 99.0}]
        result = compare(rows, rows)
        self.assertEqual(result["overlap_days"], 3)
        self.assertEqual(result["close_diff_bps_median"], 0.0)
        self.assertAlmostEqual(result["daily_return_correlation"], 1.0)


if __name__ == "__main__":
    unittest.main()
