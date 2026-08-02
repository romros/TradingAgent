import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_campaign


class ImportCampaignTest(unittest.TestCase):
    def draft(self):
        return {
            "campaign_id": "c1", "family": "f1",
            "source_artifacts": [{"path": "result.json", "role": "result"}],
            "observations": {"trades": 12},
            "assessment": {
                "decision": "REJECT", "insight_code": "LOW_SAMPLE_OR_VALIDATION_FAIL",
                "reason": "Mostra insuficient.", "next_test": "Usar dades noves.",
                "evidence_status": "tested",
            },
        }

    def test_hashes_source_without_copying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "result.json").write_text('{"large": "artifact"}', encoding="utf-8")
            result = import_campaign.normalize(self.draft(), root)
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(len(result["source_artifacts"][0]["sha256"]), 64)
        self.assertNotIn("large", str(result))

    def test_rejects_parent_path(self):
        draft = self.draft()
        draft["source_artifacts"][0]["path"] = "../result.json"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                import_campaign.normalize(draft, Path(directory))

    def test_rejects_unknown_decision(self):
        draft = self.draft()
        draft["assessment"]["decision"] = "MAYBE"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                import_campaign.normalize(draft, Path(directory))


if __name__ == "__main__":
    unittest.main()
