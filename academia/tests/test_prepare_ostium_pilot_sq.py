import sqlite3
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import prepare_ostium_pilot_sq as pilot


class PrepareOstiumPilotSqTest(unittest.TestCase):
    def test_rewrite_replaces_active_and_dormant_resources(self):
        build = b'''<Settings><Data><Setups><Setup><Chart symbol="OLD" /></Setup></Setups></Data>
        <Rankings><StopCondition /></Rankings><CrossChecks use="false"><RetestOnAdditionalMarkets>
        <Settings><Setups><Setup><Chart symbol="HIDDEN" /></Setup></Setups></Settings></RetestOnAdditionalMarkets></CrossChecks>
        <CustomData /><Resources><Symbols><Symbol name="OLD"><InstrumentInfo instrument="OLD" /></Symbol></Symbols>
        <Instruments><InstrumentInfo instrument="OLD" /></Instruments></Resources>
        <Architecture>EnterAtStop Highest Lowest ATR</Architecture></Settings>'''
        symbol = ET.fromstring('<Symbol name="NEW"><InstrumentInfo instrument="NEW" /></Symbol>')
        files = {"config.xml": b'<Project name="old"/>', "Build-Task1.xml": build}
        project = {"project": "new-project", "symbol": "NEW", "spread": "12", "slippage": "6"}
        result = pilot.rewrite(files, project, symbol)
        root = ET.fromstring(result["Build-Task1.xml"])
        self.assertEqual({c.get("symbol") for c in root.findall(".//Setup/Chart")}, {"NEW"})
        self.assertEqual(root.find(".//Setup").get("dateTo"), "2021.12.31")
        self.assertEqual(root.find(".//Resources/Symbols/Symbol").get("name"), "NEW")
        self.assertEqual(root.find(".//StopCondition").get("minutes"), "10")

    def test_missing_dormant_setup_is_rejected(self):
        build = b'''<Settings><Data><Setups><Setup><Chart symbol="OLD" /></Setup></Setups></Data>
        <Rankings><StopCondition /></Rankings><CrossChecks use="false" />
        <CustomData /><Resources><Symbols /><Instruments /></Resources>
        <Architecture>EnterAtStop Highest Lowest ATR</Architecture></Settings>'''
        symbol = ET.fromstring('<Symbol name="NEW"><InstrumentInfo instrument="NEW" /></Symbol>')
        with self.assertRaisesRegex(ValueError, "main and dormant"):
            pilot.rewrite({"config.xml": b'<Project name="old"/>', "Build-Task1.xml": build},
                          {"project": "p", "symbol": "NEW", "spread": "1", "slippage": "1"}, symbol)

    def test_risk_campaign_enforces_one_pct_sizing_and_fifteen_pct_drawdown(self):
        root = ET.fromstring('''<Settings><RiskMoneyManagement><MoneyManagement>
        <Method type="FixedSize" use="true"><Params><Param key="Size">1</Param></Params></Method>
        <Method type="RiskFixedBalancePct" use="false"><Params><Param key="Risk">5</Param></Params></Method>
        </MoneyManagement><RiskManagement maxDrawdown="30" /></RiskMoneyManagement>
        <Rankings><Conditions /></Rankings></Settings>''')
        pilot.set_risk_sizing(root, 1, 15)
        self.assertEqual(root.find(".//Method[@type='FixedSize']").get("use"), "false")
        risk = root.find(".//Method[@type='RiskFixedBalancePct']")
        self.assertEqual(risk.get("use"), "true")
        self.assertEqual(risk.find(".//*[@key='Risk']").text, "1")
        condition = root.findall(".//Rankings/Conditions/Condition")[-1]
        self.assertEqual(condition.find("./Left-Side/Column-Value").get("column"), "DrawdownPct")
        self.assertEqual(condition.find("./Comparator").get("value"), "<=")
        self.assertEqual(condition.find("./Right-Side/Numeric-Value").get("value"), "15")


if __name__ == "__main__":
    unittest.main()
