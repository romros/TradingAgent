import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from run_sq_gui_pilot import budget_decision, engine_update, project_preflight


class SqAttemptControllerTest(unittest.TestCase):
    def test_preflight_rejects_unresolved_or_multitask_project(self):
        with self.assertRaisesRegex(ValueError, "unresolved"):
            project_preflight({"projects": [{"projectName": "P", "tasks": 1, "hasUnresolvedResources": True}]}, "P")
        with self.assertRaisesRegex(ValueError, "exactly one task"):
            project_preflight({"projects": [{"projectName": "P", "tasks": 2, "hasUnresolvedResources": False}]}, "P")

    def test_budget_uses_preventive_watermark_and_hard_limit(self):
        self.assertEqual(budget_decision(899, 900, 1000), "CONTINUE")
        self.assertEqual(budget_decision(900, 900, 1000), "REQUEST_CONTROL")
        self.assertEqual(budget_decision(1001, 900, 1000), "HARD_BUDGET_EXCEEDED")

    def test_extracts_real_attempt_counter(self):
        message = json.dumps({"projectData": {"name": "P", "channels": [
            {"name": "engine-channel", "data": {"totalJobsDone": 123, "strategies": 4}}
        ]}})
        self.assertEqual(engine_update(message, "P")["totalJobsDone"], 123)
        self.assertIsNone(engine_update(message, "OTHER"))


if __name__ == "__main__":
    unittest.main()
