import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_builder_runs import compare


def run(method, attempted=2000, seconds=60):
    return {
        "method": method,
        "attempted": attempted,
        "wall_clock_seconds": seconds,
        "data_sha256": "data",
        "search_space_sha256": "space",
        "filters_sha256": "filters",
        "engine": "MetaTrader4",
        "timeframe": "H4",
        "strategies": [{"metrics": {"profit_factor": 1.2}}, {"metrics": {"profit_factor": 1.4}}],
    }


class BuilderComparisonTests(unittest.TestCase):
    def test_equal_attempts_passes_and_summarizes_distribution(self):
        result = compare(run("random"), run("genetic"), "equal_attempts")
        self.assertTrue(result["comparable"])
        self.assertAlmostEqual(result["runs"][0]["distributions"]["profit_factor"]["median"], 1.3)

    def test_missing_attempts_rejects_equal_attempt_contract(self):
        left = run("random", attempted=None)
        result = compare(left, run("genetic"), "equal_attempts")
        self.assertFalse(result["comparable"])
        self.assertIn("attempt_count_missing", result["reasons"])

    def test_frozen_context_mismatch_rejects(self):
        right = run("genetic")
        right["filters_sha256"] = "changed"
        self.assertIn("frozen_context_mismatch", compare(run("random"), right, "equal_attempts")["reasons"])


if __name__ == "__main__":
    unittest.main()
