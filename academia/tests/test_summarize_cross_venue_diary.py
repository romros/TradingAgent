import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import summarize_cross_venue_diary


class CrossVenueDiaryTest(unittest.TestCase):
    def test_daily_summary_does_not_infer_cross_venue_basis(self):
        rows = [
            {"captured_at": "2026-08-13T10:00:00Z", "sources": {"hyperliquid_xyz": [
                {"venue_contract": "xyz:GOLD", "mark": 100, "oracle": 101,
                 "impact_spread_bps": 2, "funding_raw": 0.001,
                 "open_interest_base": 10, "day_notional_volume_usd": 1000}]}, "errors": {}},
            {"captured_at": "2026-08-13T11:00:00Z", "sources": {"hyperliquid_xyz": [
                {"venue_contract": "xyz:GOLD", "mark": 102, "oracle": 102,
                 "impact_spread_bps": 4, "funding_raw": -0.001,
                 "open_interest_base": 12, "day_notional_volume_usd": 1200}]}, "errors": {}},
        ]
        result = summarize_cross_venue_diary.summarize(rows)
        cell = result["days"]["2026-08-13"]["hyperliquid_xyz:xyz:GOLD"]
        self.assertEqual(cell["snapshots"], 2)
        self.assertEqual(cell["spread_bps_median"], 3)
        self.assertAlmostEqual(cell["return_pct"], 2)
        self.assertAlmostEqual(cell["open_interest_change_pct"], 20)
        self.assertFalse(result["cross_venue_basis_authorized"])


if __name__ == "__main__":
    unittest.main()
