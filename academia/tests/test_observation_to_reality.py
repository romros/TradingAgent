import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import observation_to_reality


class ObservationToRealityTest(unittest.TestCase):
    def load(self, name):
        return json.loads((ROOT / "experiments/observations" / name).read_text())

    def test_real_rejections_are_supported_by_metrics(self):
        names = [
            "alquimia-eurusd-h4-2026-08.json",
            "intraday-fx-six-families-2026-08.json",
            "small-investor-d1-2026-08.json",
            "sq-0423850-xau-h4-2026-08.json",
        ]
        results = [observation_to_reality.assess_observation(self.load(name)) for name in names]
        self.assertTrue(all(result["decision"] == "DESCARTAR" for result in results))
        self.assertTrue(all(result["metric_consistency_verified"] for result in results))

    def test_partial_real_candidates_stay_incomplete(self):
        names = [
            "alquimia-xau-h4-07893-is-2026-08.json",
            "alquimia-eurusd-h4-41133-windows-2026-08.json",
        ]
        results = [observation_to_reality.assess_observation(self.load(name)) for name in names]
        self.assertTrue(all(result["decision"] == "INCOMPLET" for result in results))
        self.assertTrue(all(result["missing_before_reality_gate"] for result in results))

    def test_does_not_trust_an_unsupported_reject_label(self):
        item = self.load("alquimia-eurusd-h4-2026-08.json")
        item["observations"]["cost_base"]["metrics"]["net_expectancy_usdc"] = 1
        result = observation_to_reality.assess_observation(item)
        self.assertEqual(result["decision"], "INCOMPLET")
        self.assertFalse(result["metric_consistency_verified"])

    def test_markdown_is_readable_and_bounded(self):
        result = observation_to_reality.assess_observation(self.load("small-investor-d1-2026-08.json"))
        report = observation_to_reality.render_markdown([result])
        self.assertIn("DESCARTAR", report)
        self.assertIn("No reobre artifacts externs", report)


if __name__ == "__main__":
    unittest.main()
