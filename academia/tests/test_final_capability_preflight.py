import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import final_capability_preflight


class FinalCapabilityPreflightTest(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "experiments/pending/build143-final-capability-tests.json"
        self.plan = json.loads(path.read_text())

    def test_busy_sq_and_missing_cow_block_execution(self):
        result = final_capability_preflight.assess(self.plan, active_sq_projects=1, runtime_ready=False)
        self.assertFalse(result["ready"])
        self.assertIn("sq_busy:1", result["blockers"])
        self.assertIn("cow_runtime_not_proven", result["blockers"])

    def test_ready_only_when_idle_and_runtime_proven(self):
        result = final_capability_preflight.assess(self.plan, active_sq_projects=0, runtime_ready=True)
        self.assertTrue(result["ready"])

    def test_holdout_or_external_write_root_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["write_root"] = "/tmp/sq"
        plan["tests"][0]["uses_holdout"] = True
        result = final_capability_preflight.assess(plan, active_sq_projects=0, runtime_ready=True)
        self.assertIn("write_root_outside_academia", result["blockers"])
        self.assertIn("holdout_enabled:builder-improver", result["blockers"])


if __name__ == "__main__":
    unittest.main()
