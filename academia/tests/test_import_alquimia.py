import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_alquimia


class ImportAlquimiaTest(unittest.TestCase):
    def test_temporal_pass_cost_fail_is_rejected(self):
        temporal = {"input_count": 1, "survivor_count": 1, "decisions": [
            {"strategy": "S1", "passed": True, "metrics": {"trades": 100}, "checks": {}}
        ]}
        costs = {"orders": 100, "scenarios": [{"name": "base", "passed": False,
                 "assumptions": {}, "metrics": {"net_profit_factor": 0.8}, "monte_carlo": {}}]}
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.write_text("temporal"); b.write_text("costs")
            result = import_alquimia.normalize("c", "f", temporal, costs, a, b)
        self.assertEqual(result["assessment"]["decision"], "REJECT")
        self.assertEqual(result["assessment"]["insight_code"], "TEMPORAL_PASS_COST_FAIL")

    def test_missing_base_scenario_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x"; path.write_text("x")
            with self.assertRaises(ValueError):
                import_alquimia.normalize("c", "f", {"decisions": []}, {"scenarios": []}, path, path)


if __name__ == "__main__":
    unittest.main()
