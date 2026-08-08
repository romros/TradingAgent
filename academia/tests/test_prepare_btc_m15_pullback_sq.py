import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import prepare_btc_m15_pullback_sq as prepare


class PrepareBtcM15PullbackSqTest(unittest.TestCase):
    def test_signal_allowlist_contains_both_required_families_only(self):
        self.assertTrue(any(key.startswith("MA") for key in prepare.SIGNALS))
        self.assertTrue(any(key.startswith("RSI") for key in prepare.SIGNALS))
        self.assertNotIn("EnterAtStop", prepare.SIGNALS)

    def test_numeric_condition_serializes_frozen_gate(self):
        root = ET.Element("Conditions")
        prepare.numeric_condition(root, "NumberOfTrades", "Number of trades", ">=", 150)
        condition = root.find("Condition")
        self.assertEqual(condition.find("Comparator").get("value"), ">=")
        self.assertEqual(condition.find(".//Numeric-Value").get("value"), "150")

    def test_project_name_is_campaign_specific(self):
        self.assertEqual(prepare.PROJECT, "ACADEMIA_BTC_M15_TREND_PULLBACK_V1")


if __name__ == "__main__":
    unittest.main()
