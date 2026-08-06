import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import audit_volatility_expansion_artifacts as auditor


class AuditVolatilityExpansionArtifactsTest(unittest.TestCase):
    def _artifact(self, directory: Path, name: str, text: str) -> Path:
        path = directory / name
        with ZipFile(path, "w") as archive:
            archive.writestr("strategy_Portfolio.xml", text)
        return path

    def test_requires_one_token_from_each_semantic_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = self._artifact(root, "good.sqx", "ATRFalling BBBarClosesAboveUp ATR StopLoss")
            bad = self._artifact(root, "bad.sqx", "ATRFalling ATR StopLoss")
            self.assertTrue(auditor.audit(good)["passed"])
            self.assertFalse(auditor.audit(bad)["passed"])
            summary = auditor.audit_directory(root)
            self.assertEqual(summary["artifacts_checked"], 2)
            self.assertEqual(summary["artifacts_passed"], 1)

    def test_unreadable_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.sqx"
            path.write_text("not a zip")
            result = auditor.audit(path)
            self.assertFalse(result["passed"])
            self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
