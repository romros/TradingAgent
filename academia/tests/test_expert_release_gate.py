import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import expert_release_gate


class ExpertReleaseGateTest(unittest.TestCase):
    def release(self):
        return json.loads((ROOT / "packages/strategyquant/releases/alquimia-expert-v1.json").read_text())

    def test_v1_release_is_honestly_blocked_by_two_capabilities(self):
        result = expert_release_gate.gate(self.release())
        self.assertFalse(result["passed"])
        self.assertEqual(result["battle_score"], 1)
        self.assertEqual(result["blind_actual"], "DESCARTAR")
        self.assertGreaterEqual(result["discovered_tests"], 76)
        self.assertFalse(result["checks"]["all_capabilities_tested"])
        self.assertEqual([gap["id"] for gap in result["tested_capability_coverage"]["gaps"]],
                         ["builder-improver", "export-crossplatform"])

    def test_cannot_hide_an_open_boundary(self):
        release = self.release()
        release["open_boundaries"].remove("improver_slpt_only_structural_proof")
        result = expert_release_gate.gate(release)
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["boundaries_preserved"])


if __name__ == "__main__":
    unittest.main()
