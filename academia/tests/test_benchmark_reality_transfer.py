import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import benchmark_reality_transfer


class RealityTransferBenchmarkTest(unittest.TestCase):
    def test_battle_suite(self):
        suite = json.loads((ROOT / "experiments/examples/reality-transfer-battle-cases.json").read_text())
        result = benchmark_reality_transfer.benchmark(suite)
        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["cases"], 5)

    def test_wrong_expectation_is_visible(self):
        suite = {"id": "deliberate-failure", "cases": [{
            "id": "x", "expected_decision": "OBRIR HOLDOUT", "input": {"candidate_id": "x"},
        }]}
        result = benchmark_reality_transfer.benchmark(suite)
        self.assertFalse(result["passed"])
        self.assertEqual(result["details"][0]["actual"], "INCOMPLET")


if __name__ == "__main__":
    unittest.main()
