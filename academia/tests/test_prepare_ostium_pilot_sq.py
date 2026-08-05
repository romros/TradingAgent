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


if __name__ == "__main__":
    unittest.main()
