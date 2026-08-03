import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from msft_source_parity import aggregate_regular_session, compare, load_ostium_parquet_m1


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

    def test_quarantined_parquet_loader_is_symbol_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "MSFT" / "tf=1m" / "year=2026" / "month=07"
            target.mkdir(parents=True)
            duckdb.connect(":memory:").execute(
                'COPY (SELECT 1782916200::BIGINT "ts", 100.0::DOUBLE "open", '
                '101.0::DOUBLE "high", 99.0::DOUBLE "low", 100.5::DOUBLE "close") '
                f"TO '{target / 'data.parquet'}' (FORMAT PARQUET)"
            )
            rows = load_ostium_parquet_m1(root, "MSFT")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["close"], 100.5)
            self.assertEqual(load_ostium_parquet_m1(root, "NVDAUSD"), [])


if __name__ == "__main__":
    unittest.main()
