import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import strategy_review


class StrategyReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "experiments/examples/three-candidates.json"
        cls.candidates = json.loads(path.read_text())

    def test_three_decision_paths(self):
        decisions = [strategy_review.review(item)["decision"] for item in self.candidates]
        self.assertEqual(decisions, ["DESCARTAR", "PROVA DIRIGIDA", "CONTINUAR"])

    def test_missing_input_fails_closed(self):
        result = strategy_review.review({"id": "incomplet"})
        self.assertEqual(result["decision"], "DESCARTAR")


if __name__ == "__main__":
    unittest.main()
