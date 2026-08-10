import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from screen_xau_gld_holdings import build_episodes, summarize


class XauGldHoldingsTests(unittest.TestCase):
    def test_factor_waits_one_full_week_before_entry(self):
        weeks = [date(2020, 1, 3), date(2020, 1, 10), date(2020, 1, 17), date(2020, 1, 24), date(2020, 1, 31)]
        rows = [
            {"week": day, "date": day, "price": price, "ounces": ounces}
            for day, price, ounces in zip(weeks, [100, 100, 110, 120, 120], [100, 102, 103, 103, 100])
        ]
        episodes = build_episodes(rows, lookback=1, threshold_pct=1)
        self.assertEqual(episodes[0]["entry"], date(2020, 1, 17))
        self.assertEqual(episodes[0]["exit"], date(2020, 1, 24))
        self.assertAlmostEqual(episodes[0]["gross_return"], 120 / 110 - 1)

    def test_stress_financing_depends_on_duration(self):
        episode = {"entry": date(2020, 1, 1), "exit": date(2020, 1, 31), "signal": 1, "gross_return": 0.02}
        result = summarize([episode], execution_bps=10, annual_financing_pct=12)
        expected = 0.02 - 0.001 - 0.12 * 30 / 365
        self.assertAlmostEqual(result["net_return_sum_pct"], round(100 * expected, 6))


if __name__ == "__main__":
    unittest.main()
