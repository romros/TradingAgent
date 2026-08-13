import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).parents[1] / "projects" / "wolfpack"
spec = importlib.util.spec_from_file_location("wolfpack_maintain", HERE / "maintain.py")
maintain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintain)


class WolfpackMaintenanceTest(unittest.TestCase):
    def test_missing_feeds_are_reported_unhealthy(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            fake_brief = {"decision": "OBSERVE", "criticality_ceiling": "C1"}
            def run(command, check):
                payload = {"closed": []} if command[-1].endswith("paper-latest.json") else fake_brief
                Path(command[-1]).write_text(json.dumps(payload))
            with patch.object(maintain.subprocess, "run", side_effect=run):
                result = maintain.checkpoint(HERE, base / "diary", base / "follow",
                                             base / "heartbeat", base / "out")
            self.assertFalse(result["health"]["diary_healthy"])
            self.assertFalse(result["health"]["follower_healthy"])
            self.assertEqual(result["brief"]["criticality_ceiling"], "C1")
            self.assertTrue((base / "out" / "paper-latest.json").exists())


if __name__ == "__main__":
    unittest.main()
