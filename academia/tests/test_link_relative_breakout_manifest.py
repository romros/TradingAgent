import json
import unittest
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "experiments" / "pending" / "link-relative-breakout-replication-v40.json"


class LinkRelativeBreakoutManifestTest(unittest.TestCase):
    def test_geometry_reconstructs_v39_and_is_not_live(self):
        data = json.loads(MANIFEST.read_text())
        anchor = 8.7925
        levels = {}
        for direction, geometry in data["geometry"].items():
            trigger = anchor * (1 + geometry["trigger_anchor_pct"] / 100)
            levels[direction] = {
                "trigger": trigger,
                "stop": trigger * (1 + geometry["stop_from_trigger_pct"] / 100),
                "target_1": trigger * (1 + geometry["target_1_from_trigger_pct"] / 100),
                "target_2": trigger * (1 + geometry["target_2_from_trigger_pct"] / 100),
            }
        self.assertAlmostEqual(levels["short"]["trigger"], 8.72)
        self.assertAlmostEqual(levels["short"]["target_2"], 8.40)
        self.assertAlmostEqual(levels["long"]["trigger"], 8.865)
        self.assertAlmostEqual(levels["long"]["target_2"], 9.02)
        self.assertFalse(data["live_trading_authorized"])
        self.assertEqual(data["success_gate"]["minimum_closed_replications"], 10)

