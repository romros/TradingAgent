import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import experiment_gate


class ExperimentGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = Path(__file__).resolve().parents[1] / "experiments/examples/wfm-region-synthetic.json"
        cls.valid = json.loads(fixture.read_text())

    def test_valid_fixture_is_only_tested(self):
        result = experiment_gate.assess(self.valid)
        self.assertTrue(result["eligible"])
        self.assertEqual(result["max_evidence_status"], "tested")

    def test_holdout_peek_blocks_evidence(self):
        data = copy.deepcopy(self.valid)
        data["holdout_peeks"] = 1
        result = experiment_gate.assess(data)
        self.assertFalse(result["eligible"])
        self.assertIn("holdout_not_blind", result["failures"])

    def test_attempt_budget_is_enforced(self):
        data = copy.deepcopy(self.valid)
        data["attempts_observed"] = 10
        self.assertIn("attempt_budget_exceeded", experiment_gate.assess(data)["failures"])

    def test_costs_and_hashes_are_required(self):
        data = copy.deepcopy(self.valid)
        del data["costs"]["slippage"]
        data["artifacts"]["config_sha256"] = "bad"
        failures = experiment_gate.assess(data)["failures"]
        self.assertIn("missing_cost:slippage", failures)
        self.assertIn("invalid_artifact:config_sha256", failures)


if __name__ == "__main__":
    unittest.main()
