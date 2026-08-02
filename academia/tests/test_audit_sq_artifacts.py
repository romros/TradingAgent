import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_sq_artifacts


class SqArtifactAuditTest(unittest.TestCase):
    def test_separates_configured_task_from_executed_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "Pilot"
            project.mkdir()
            with zipfile.ZipFile(project / "project.cfx", "w") as archive:
                archive.writestr("config.xml", '<Project><Tasks><Task type="Retest"/></Tasks></Project>')
            with zipfile.ZipFile(project / "candidate.sqx", "w") as archive:
                archive.writestr("Results/WF: 5 runs/dailyEquity.bin", b"")
            result = audit_sq_artifacts.audit(root)
            self.assertEqual(result["configured_task_types"], {"Retest": 1})
            self.assertEqual(result["executed_result_members"]["walk_forward"], 1)
            self.assertEqual(result["executed_result_members"]["monte_carlo"], 0)


if __name__ == "__main__":
    unittest.main()
