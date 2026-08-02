import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import campaign_preflight


class CampaignPreflightTest(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        self.plan = json.loads((root / "experiments/examples/campaign-preregistration.json").read_text())
        self.memory = json.loads((root / "experiments/failure-memory.json").read_text())

    def test_unfrozen_draft_does_not_start(self):
        result = campaign_preflight.assess(self.plan, self.memory)
        self.assertFalse(result["ready"])
        self.assertIn("protocol_not_frozen", result["blockers"])

    def test_complete_new_family_can_start_cheap_stage(self):
        plan = copy.deepcopy(self.plan)
        plan["frozen"] = True
        plan["periods"] = {"development": "2004-2014", "validation": "2015-2020", "holdout": "2021-2025"}
        plan["costs"] = {"spread": "measured_bid_ask", "commission": 0, "slippage": "1_bps"}
        result = campaign_preflight.assess(plan, self.memory)
        self.assertTrue(result["ready"])
        self.assertEqual(result["decision"], "GENERATE_CHEAP_STAGE")

    def test_known_failed_family_must_be_acknowledged(self):
        plan = copy.deepcopy(self.plan)
        plan["frozen"] = True
        plan["family"] = "intraday_fx_4h"
        result = campaign_preflight.assess(plan, self.memory)
        self.assertIn("unacknowledged_prior_failure:intraday_fx_six_families_20260801", result["blockers"])

    def test_linked_failure_requires_material_difference(self):
        plan = copy.deepcopy(self.plan)
        plan["frozen"] = True
        plan["prior_failure_ids"] = ["intraday_fx_six_families_20260801"]
        result = campaign_preflight.assess(plan, self.memory)
        self.assertIn("difference_from_prior_missing", result["blockers"])


if __name__ == "__main__":
    unittest.main()
