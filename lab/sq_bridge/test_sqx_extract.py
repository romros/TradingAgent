import tempfile
import unittest
import zipfile
import re
from pathlib import Path

try:
    from lab.sq_bridge.sqx_extract import extract
except ModuleNotFoundError:
    from sqx_extract import extract


STRATEGY = b'''<StrategyFile><Strategy><Rules><Events><Event key="OnBarUpdate">
<Rule type="Signal"><signals>
<signal variable="L"><Item key="Boolean"><Param key="#Value#">true</Param></Item></signal>
<signal variable="S"><Item key="Boolean"><Param key="#Value#">true</Param></Item></signal>
<signal variable="33333333-1111-2222-3333-333333333333"><Item key="Boolean"><Param key="#Value#">false</Param></Item></signal>
<signal variable="33333333-2222-2222-3333-333333333333"><Item key="Boolean"><Param key="#Value#">false</Param></Item></signal>
</signals></Rule>
<Rule type="IfThen" name="Long entry"><If><Item><Param key="#Variable#">L</Param></Item></If><Then><Item key="EnterAtMarket"><Param key="#Direction#">1</Param><Param key="#AllowDuplicateTrades#">false</Param><Param key="#ExitAfterBars.ExitAfterBars#">5</Param><Param key="#StopLoss.StopLoss#"><Formula key="SQ.Formulas.SLPT.ATRBasedValue"><Param key="#Value#">2</Param><Param key="#AtrPeriod#">14</Param></Formula></Param><Param key="#ProfitTarget.ProfitTarget#"><Formula key="SQ.Formulas.SLPT.None"/></Param></Item></Then></Rule>
<Rule type="IfThen" name="Short entry"><If><Item><Param key="#Variable#">S</Param></Item></If><Then><Item key="EnterAtMarket"><Param key="#Direction#">-1</Param><Param key="#AllowDuplicateTrades#">false</Param><Param key="#ExitAfterBars.ExitAfterBars#">5</Param><Param key="#StopLoss.StopLoss#"><Formula key="SQ.Formulas.SLPT.ATRBasedValue"><Param key="#Value#">2</Param><Param key="#AtrPeriod#">14</Param></Formula></Param><Param key="#ProfitTarget.ProfitTarget#"><Formula key="SQ.Formulas.SLPT.None"/></Param></Item></Then></Rule>
</Event></Events></Rules></Strategy></StrategyFile>'''
SETTINGS = b'''<ResultsGroup><ValuesMap><StrategyName key="StrategyName">T</StrategyName><Symbol key="Symbol">NVDA</Symbol><Timeframe key="Timeframe">M15</Timeframe><E key="ExitAtEndOfDay.ExitAtEndOfDay">false</E><T key="ExitAtEndOfDay.EODExitTime">1530</T><F key="ExitOnFriday.ExitOnFriday">false</F><FT key="ExitOnFriday.FridayExitTime">1600</FT><S key="Slippage">0.0</S></ValuesMap></ResultsGroup>'''


class SqxExtractTest(unittest.TestCase):
    def _write_sqx(self, directory, strategy=STRATEGY):
        path = Path(directory) / "x.sqx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("strategy_Portfolio.xml", strategy)
            archive.writestr("settings.xml", SETTINGS)
            archive.writestr("version.txt", "3")
        return path

    def test_supported_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp))
            self.assertTrue(result["supported"])
            self.assertEqual(result["execution"]["eod_exit_time_hhmm"], 1530)
            self.assertEqual(result["entry_condition_counts"], {"long": 1, "short": 1})
            self.assertEqual(result["maximum_entry_conditions"], 1)

    def test_counts_predicates_but_not_their_indicator_operands(self):
        long_signal = b'''<Item key="AND">
          <Item key="IsGreater"><Block><Item key="SMA"/></Block><Block><Item key="Number"/></Block></Item>
          <Item key="IsRising"><Block><Item key="RSI"/></Block></Item>
        </Item>'''
        short_signal = b'''<Item key="AND">
          <Item key="IsLower"><Block><Item key="Close"/></Block><Block><Item key="SMA"/></Block></Item>
          <Item key="CrossesBelow"><Block><Item key="EMA"/></Block><Block><Item key="EMA"/></Block></Item>
          <Item key="BarDayOfWeekIs"/>
        </Item>'''
        strategy = STRATEGY.replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>', long_signal, 1
        ).replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>', short_signal, 1
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp, strategy))
        self.assertEqual(result["entry_condition_counts"], {"long": 2, "short": 3})
        self.assertEqual(result["maximum_entry_conditions"], 3)

    def test_inactive_direction_counts_zero(self):
        strategy = re.sub(
            rb'(<Rule type="IfThen" name="Short entry"><If>.*?</If>)<Then>.*?</Then></Rule>',
            rb'\1<Then/></Rule>', STRATEGY, count=1, flags=re.DOTALL,
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp, strategy))
        self.assertEqual(result["entry_condition_counts"], {"long": 1, "short": 0})
        self.assertEqual(result["maximum_entry_conditions"], 1)

    def test_rejects_missing_signal_reference(self):
        strategy = STRATEGY.replace(b'>L</Param>', b'>MISSING</Param>', 1)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "signal inexistent"):
                extract(self._write_sqx(tmp, strategy))

    def test_rejects_empty_and(self):
        strategy = STRATEGY.replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>',
            b'<Item key="AND"/>', 1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "AND sense condicions"):
                extract(self._write_sqx(tmp, strategy))

    def test_accepts_highest_over_supported_sq_price_source(self):
        strategy = STRATEGY.replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>',
            b'<Item key="Highest"><Param key="#ComputedFrom#">4</Param></Item>', 1)
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp, strategy))
        self.assertTrue(result["supported"])

    def test_rejects_highest_over_unknown_sq_price_source(self):
        strategy = STRATEGY.replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>',
            b'<Item key="Highest"><Param key="#ComputedFrom#">99</Param></Item>', 1)
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp, strategy))
        self.assertFalse(result["supported"])
        self.assertIn("INVALID_PRICE_COMPUTED_FROM",
                      result["unsupported_nodes_or_formulas"])

    def test_rejects_roc_from_unknown_price_source(self):
        strategy = STRATEGY.replace(
            b'<Item key="Boolean"><Param key="#Value#">true</Param></Item>',
            b'<Item key="IsRising"><Block><Item key="ROC"><Param key="#ComputedFrom#">6</Param></Item></Block></Item>', 1)
        with tempfile.TemporaryDirectory() as tmp:
            result = extract(self._write_sqx(tmp, strategy))
        self.assertFalse(result["supported"])
        self.assertIn("NON_CLOSE_COMPUTED_FROM", result["unsupported_nodes_or_formulas"])


if __name__ == "__main__": unittest.main()
