import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import next_test


class NextTestTest(unittest.TestCase):
    def test_cost_failure_does_not_recommend_optimization(self):
        action = next_test.recommend("COST_FAIL")["next_test"]
        self.assertIn("Aturar", action)
        self.assertNotIn("optimitzar", action.lower())

    def test_unknown_risk_asks_for_missing_data(self):
        self.assertIn("dada mínima", next_test.recommend("UNKNOWN")["next_test"])


if __name__ == "__main__":
    unittest.main()
