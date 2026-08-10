import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from screen_eurusd_policy_differential import build_episodes, summarize


class EurusdPolicyDifferentialTests(unittest.TestCase):
    def test_signal_waits_one_week_and_groups_contiguous_state(self):
        weeks = [date(2020, 1, 3), date(2020, 1, 10), date(2020, 1, 17), date(2020, 1, 24), date(2020, 1, 31)]
        price = dict(zip(weeks, [1.0, 1.0, 1.1, 1.2, 1.2]))
        ecb = dict(zip(weeks, [0.0, 0.5, 0.6, 0.6, 0.0]))
        fed = {week: 0.0 for week in weeks}
        episodes = build_episodes(price, ecb, fed, lookback=1, threshold=0.25)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0]["entry"], date(2020, 1, 17))
        self.assertEqual(episodes[0]["exit"], date(2020, 1, 24))
        self.assertAlmostEqual(episodes[0]["gross_return"], 1.2 / 1.1 - 1)

    def test_stress_cost_includes_holding_time(self):
        rows = [{"entry": date(2020, 1, 1), "exit": date(2020, 1, 8), "signal": 1, "gross_return": 0.01}]
        result = summarize(rows, execution_bps=10, annual_financing_pct=10)
        expected = 0.01 - 0.001 - 0.10 * 7 / 365
        self.assertAlmostEqual(result["net_return_sum_pct"], round(expected * 100, 6))


if __name__ == "__main__":
    unittest.main()
