import unittest

from spxusd_execution_economics import audit, liquidation_distance_pct


class SpxusdExecutionEconomicsTest(unittest.TestCase):
    def test_official_liquidation_examples(self):
        self.assertAlmostEqual(liquidation_distance_pct(20, 200), 4.875)
        self.assertAlmostEqual(liquidation_distance_pct(100, 200), 0.875)
        self.assertAlmostEqual(liquidation_distance_pct(200, 200), 0.375)

    def test_one_percent_risk_sizing(self):
        result = audit(capitals=(200,), stop_distances_pct=(0.5,))
        row = result["sizing_examples"][0]
        self.assertEqual(row["risk_usdc"], 2)
        self.assertEqual(row["notional_usdc"], 400)
        self.assertEqual(row["effective_leverage_if_all_capital"], 2)
        self.assertEqual(row["opening_fee_usdc"], 0.04)
        self.assertEqual(row["breakeven_stress_oracle_not_refunded_bps"], 3.5)
        self.assertAlmostEqual(row["single_closed_snapshot_entry_cost_bps"], 2.450807)

    def test_single_closed_snapshot_still_blocks_paper(self):
        result = audit()
        self.assertEqual(result["gates"]["paper"], "BLOCKED")
        self.assertAlmostEqual(
            result["scenario_assumptions"]["single_closed_snapshot_spread_bps"], 0.9672048772
        )
        self.assertIn("measured bid-ask distribution", " ".join(result["gates"]["missing"]))


if __name__ == "__main__":
    unittest.main()
