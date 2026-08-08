import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import prepare_single_validation_sq as validation


class PrepareSingleValidationSqTest(unittest.TestCase):
    def test_rewrite_freezes_pre_holdout_period_and_gates(self):
        xml = b'''<Settings><Data><Setups><Setup dateFrom="x" dateTo="y" testPrecision="1">
        <Chart symbol="EURUSD_M1_dukas_M1_UTCMinus05" timeframe="H4" /></Setup></Setups></Data>
        <Rankings><Conditions>
        <Condition><Column-Value column="NumberOfTrades"/><Numeric-Value value="1"/></Condition>
        <Condition><Column-Value column="ProfitFactor"/><Numeric-Value value="1"/></Condition>
        <Condition><Column-Value column="DrawdownPct"/><Numeric-Value value="20"/></Condition>
        </Conditions></Rankings></Settings>'''
        result = validation.rewrite({"config.xml": b'<Project name="old"/>', "Retest-Task1.xml": xml}, "NEW")
        root = ET.fromstring(result["Retest-Task1.xml"])
        setup = root.find(".//Data/Setups/Setup")
        self.assertEqual(setup.get("dateFrom"), "2022.01.01")
        self.assertEqual(setup.get("dateTo"), "2025.07.31")
        self.assertEqual(setup.find("Chart").get("timeframe"), "D1")
        values = {c.find(".//Column-Value").get("column"): c.find(".//Numeric-Value").get("value")
                  for c in root.findall(".//Condition")}
        self.assertEqual(values, {"NumberOfTrades": "30", "ProfitFactor": "1.10", "DrawdownPct": "15"})

    def test_rejects_wrong_symbol_template(self):
        xml = b'<Settings><Data><Setups><Setup><Chart symbol="XAU"/></Setup></Setups></Data></Settings>'
        with self.assertRaisesRegex(ValueError, "frozen EURUSD"):
            validation.rewrite({"config.xml": b'<Project/>', "Retest-Task1.xml": xml}, "NEW")


if __name__ == "__main__":
    unittest.main()
