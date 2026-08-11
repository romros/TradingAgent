import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ostium_objective_status


class OstiumObjectiveStatusTest(unittest.TestCase):
    def setUp(self):
        self.objective = json.loads((ROOT / "packages/strategyquant/ostium-500-objective.json").read_text())
        self.catalog = json.loads((ROOT / "packages/strategyquant/ostium-500-strategy-catalog.json").read_text())

    def test_current_catalog_blocks_portfolio_and_x2_claim(self):
        result = ostium_objective_status.status(self.objective, self.catalog)
        self.assertEqual(result["catalog"]["promotable_components"], 0)
        self.assertFalse(result["portfolio_ready"])
        self.assertFalse(result["x2_simulation_ready"])
        self.assertFalse(result["target_is_promise"])
        self.assertEqual(result["catalog"]["strategy_target"], [1, 6])
        self.assertEqual(result["catalog"]["preferred_diversified_range"], [3, 6])
        self.assertEqual(result["catalog"]["strategies_needed_for_portfolio"], 1)
        self.assertFalse(result["catalog"]["asset_coverage_required"])

    def test_one_component_can_open_portfolio_simulation(self):
        self.catalog["assets"][1]["promotable_components"] = ["spx-a"]
        result = ostium_objective_status.status(self.objective, self.catalog)
        self.assertTrue(result["portfolio_ready"])
        self.assertTrue(result["x2_simulation_ready"])
        self.assertEqual(result["catalog"]["assets_with_component"], ["US500/USD"])

    def test_aligned_new_component_task_passes(self):
        task = {"id": "eur-weekly", "contribution": "new_component", "asset": "EUR/USD", "expected_decision": "reject or promote", "stop_condition": "cheap gate", "uses_holdout": False}
        self.assertTrue(ostium_objective_status.task_gate(self.objective, task)["aligned"])

    def test_capability_work_and_holdout_fail(self):
        task = {"id": "sq-feature", "contribution": "tool_completeness", "asset": "EUR/USD", "expected_decision": "works", "stop_condition": "time", "uses_holdout": True}
        result = ostium_objective_status.task_gate(self.objective, task)
        self.assertFalse(result["aligned"])
        self.assertIn("contribution_outside_objective", result["errors"])
        self.assertIn("premature_holdout_use", result["errors"])


if __name__ == "__main__":
    unittest.main()
