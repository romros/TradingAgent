import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import campaign_advisor


class CampaignAdvisorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "experiments/failure-memory.json"
        cls.memory = json.loads(path.read_text())

    def test_all_known_families_produce_evidenced_rejection(self):
        for entry in self.memory["entries"]:
            with self.subTest(entry=entry["id"]):
                result = campaign_advisor.advise(self.memory, entry["family"])
                self.assertEqual(result["decision"], "DESCARTAR")
                self.assertNotEqual(result["evidencia"], "falta")
                self.assertIn("academia/experiments/observations/", result["evidencia"])
                self.assertTrue(result["no_repetir"])

    def test_unknown_family_does_not_borrow_another_edge(self):
        result = campaign_advisor.advise(self.memory, "unknown_family")
        self.assertEqual(result["decision"], "PROVA DIRIGIDA")
        self.assertEqual(result["evidencia"], "falta")

    def test_render_uses_skill_contract(self):
        result = campaign_advisor.advise(self.memory, "xauusd_h4_bollinger_long")
        rendered = campaign_advisor.render(result)
        for label in ("DECISIÓ:", "MOTIU:", "RISC PRINCIPAL:", "SEGÜENT PAS:", "EVIDÈNCIA:"):
            self.assertIn(label, rendered)


if __name__ == "__main__":
    unittest.main()
