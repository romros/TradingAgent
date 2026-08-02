import tempfile
import unittest
import zipfile
from pathlib import Path

from sqx_extract import extract


STRATEGY = b'''<StrategyFile><Strategy><Rules><Events><Event key="OnBarUpdate">
<Rule type="Signal"><signals>
<signal variable="L"><Item key="Boolean"><Param key="#Value#">true</Param></Item></signal>
<signal variable="S"><Item key="Boolean"><Param key="#Value#">true</Param></Item></signal>
<signal variable="33333333-1111-2222-3333-333333333333"><Item key="Boolean"><Param key="#Value#">false</Param></Item></signal>
<signal variable="33333333-2222-2222-3333-333333333333"><Item key="Boolean"><Param key="#Value#">false</Param></Item></signal>
</signals></Rule>
<Rule type="IfThen" name="Long entry"><If><Item><Param key="#Variable#">L</Param></Item></If><Then><Item key="EnterAtMarket"/></Then></Rule>
<Rule type="IfThen" name="Short entry"><If><Item><Param key="#Variable#">S</Param></Item></If><Then><Item key="EnterAtMarket"/></Then></Rule>
</Event></Events></Rules></Strategy></StrategyFile>'''
SETTINGS = b'''<ResultsGroup><ValuesMap><StrategyName key="StrategyName">T</StrategyName><Symbol key="Symbol">NVDA</Symbol><Timeframe key="Timeframe">M15</Timeframe><E key="ExitAtEndOfDay.ExitAtEndOfDay">true</E><T key="ExitAtEndOfDay.EODExitTime">1530</T><S key="Slippage">0.0</S></ValuesMap></ResultsGroup>'''


class SqxExtractTest(unittest.TestCase):
    def test_supported_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.sqx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("strategy_Portfolio.xml", STRATEGY)
                archive.writestr("settings.xml", SETTINGS)
                archive.writestr("version.txt", "3")
            result = extract(path)
            self.assertTrue(result["supported"])
            self.assertEqual(result["execution"]["eod_exit_time_hhmm"], 1530)


if __name__ == "__main__": unittest.main()
