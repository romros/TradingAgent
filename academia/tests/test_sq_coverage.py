import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import sq_coverage


class SqCoverageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "packages/strategyquant/coverage.json").read_text())

    def test_order_is_unique_and_complete(self):
        orders = [item["order"] for item in self.data["capabilities"]]
        self.assertEqual(orders, list(range(len(orders))))

    def test_first_tested_gap_drives_next_work(self):
        result = sq_coverage.report(self.data)
        self.assertEqual(result["minimum"], "tested")
        self.assertEqual(result["next_gap"]["id"], "builder-improver")
        self.assertEqual(result["by_status"], {"tested": 12, "operational": 2})
        self.assertEqual(result["coverage_ratio"], 0.857)

    def test_operational_coverage_remains_available_but_is_not_completion(self):
        result = sq_coverage.report(self.data, minimum="operational")
        self.assertIsNone(result["next_gap"])
        self.assertEqual(result["coverage_ratio"], 1)

    def test_evidence_ids_resolve(self):
        ids = {json.loads(path.read_text())["id"] for path in (ROOT / "sources").glob("*/*.json")}
        missing = {evidence for item in self.data["capabilities"] for evidence in item["evidence"] if evidence not in ids}
        self.assertEqual(missing, set())


if __name__ == "__main__":
    unittest.main()
