import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import prepare_volatility_expansion_sq as pivot


class PrepareVolatilityExpansionSqTest(unittest.TestCase):
    def _files(self):
        blocks = "".join(f'<Block key="{key}" use="false" />' for key in pivot.ALLOWED_BLOCKS | {"Forbidden"})
        build = f'''<Settings><Data><Setups>
        <Setup dateFrom="x" dateTo="y"><Chart symbol="EURUSD" timeframe="H4" /></Setup>
        </Setups></Data><CrossChecks use="false"><Settings><Setups>
        <Setup dateFrom="x" dateTo="y"><Chart symbol="EURUSD" timeframe="H4" /></Setup>
        </Setups></Settings></CrossChecks><Rankings><StopCondition /></Rankings>
        <RulesComplexity><Chart /></RulesComplexity><MarketSides type="long">
        <EntrySymmetry>false</EntrySymmetry><ExitSymmetry>false</ExitSymmetry></MarketSides>
        <SLPTOptions><SLRequired>false</SLRequired><SLFixedPips>true</SLFixedPips>
        <SLATR>false</SLATR><MinSLATRMultiple>1</MinSLATRMultiple><MaxSLATRMultiple>2</MaxSLATRMultiple>
        <MinSLATRPeriod>5</MinSLATRPeriod><MaxSLATRPeriod>10</MaxSLATRPeriod><PTRequired>true</PTRequired></SLPTOptions>
        <Blocks>{blocks}</Blocks><RiskMoneyManagement><MoneyManagement>
        <Method type="FixedSize" use="false" /><Method type="RiskFixedBalancePct" use="true">
        <Param key="Risk">1</Param></Method></MoneyManagement><RiskManagement maxDrawdown="15" />
        </RiskMoneyManagement></Settings>'''.encode()
        return {"config.xml": b'<Project name="old"/>', "Build-Task1.xml": build}

    def test_rewrite_freezes_d1_mechanism_and_risk(self):
        result = pivot.rewrite(self._files(), "PIVOT")
        root = ET.fromstring(result["Build-Task1.xml"])
        self.assertEqual({chart.get("timeframe") for chart in root.findall(".//Setup/Chart")}, {"D1"})
        enabled = {block.get("key") for block in root.findall(".//Block") if block.get("use") == "true"}
        self.assertEqual(enabled, pivot.ALLOWED_BLOCKS)
        self.assertEqual(root.find(".//Block[@key='Forbidden']").get("use"), "false")
        self.assertEqual(root.find(".//RulesComplexity/Chart").get("minConditions"), "2")
        self.assertEqual(root.find(".//SLPTOptions/SLATR").text, "true")
        self.assertEqual(root.find(".//MarketSides").get("type"), "both")
        self.assertEqual(root.find(".//Rankings/StopCondition").get("passedStrategies"), "20")

    def test_rejects_template_without_safe_risk_contract(self):
        files = self._files()
        files["Build-Task1.xml"] = files["Build-Task1.xml"].replace(b'maxDrawdown="15"', b'maxDrawdown="30"')
        with self.assertRaisesRegex(ValueError, "15-percent drawdown"):
            pivot.rewrite(files, "PIVOT")

    def test_accepts_equivalent_decimal_risk_representation(self):
        files = self._files()
        files["Build-Task1.xml"] = files["Build-Task1.xml"].replace(
            b'<Param key="Risk">1</Param>', b'<Param key="Risk">1.0</Param>'
        )
        pivot.rewrite(files, "PIVOT")


if __name__ == "__main__":
    unittest.main()
