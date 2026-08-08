import sys
import unittest
from datetime import datetime
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

    def test_eia_sheet_parser_reads_excel_dates_and_filters_window(self):
        serial = (datetime(2024, 1, 2).date() - datetime(1899, 12, 30).date()).days
        xml = f'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
          <row r="1"><c r="A1" t="s"><v>1</v></c><c r="B1" t="s"><v>2</v></c></row>
          <row r="2"><c r="A2" t="n"><v>{serial}</v></c><c r="B2" t="n"><v>72.5</v></c></row>
        </sheetData></worksheet>'''.encode()
        self.assertEqual(proxy.parse_eia_sheet(xml, "2024-01-01", "2024-01-03"), {"2024-01-02": 72.5})
        self.assertEqual(proxy.parse_eia_sheet(xml, "2024-02-01", "2024-02-03"), {})

    def test_no_overlap_is_not_reported_as_aligned(self):
        self.assertEqual(proxy.alignment_decision(proxy.compare({}, {})), "NO_OVERLAP")


if __name__ == "__main__":
    unittest.main()
