import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lint_sqx_semantics


def _sqx(path: Path, exit_expression: str, direction: str = "1") -> Path:
    strategy = f"""<Root><Strategy engine="MetaTrader4"><Events><Event key="OnBarUpdate">
      <Rule name="Trading signals"><signals>
        <signal variable="entry-long"><Item key="SMA"><Param key="#Period#">20</Param></Item></signal>
        <signal variable="exit-long">{exit_expression}</signal>
      </signals></Rule>
      <Rule name="Long entry"><If><Item key="BooleanVariable"><Param key="#Variable#">entry-long</Param></Item></If>
        <Then><Item key="EnterAtMarket"><Param key="#Symbol#">Current</Param><Param key="#Direction#">{direction}</Param><Param key="#Size#"><Formula key="SQ.Formulas.Size.UseGlobalMM"/></Param></Item></Then>
      </Rule>
    </Event></Events></Strategy></Root>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("strategy_Portfolio.xml", strategy)
    return path


class SqxSemanticLintTest(unittest.TestCase):
    def test_rejects_and_false_while_preserving_entry_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"><Param key="#Period#">14</Param></Item>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="AND"><Block><Item key="ATR"/></Block><Block><Item key="Boolean"><Param key="#Value#">false</Param></Item></Block></Item>')
            result = lint_sqx_semantics.lint(candidate, base)
            self.assertFalse(result["passed"])
            self.assertTrue(result["frozen_contract"]["entry_and_orders_preserved"])
            self.assertEqual(result["findings"][0]["code"], "CONSTANT_SIGNAL")

    def test_rejects_frozen_order_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"/>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="ATR"/>', direction="-1")
            result = lint_sqx_semantics.lint(candidate, base)
            self.assertFalse(result["passed"])
            self.assertFalse(result["frozen_contract"]["entry_and_orders_preserved"])
            self.assertEqual(result["findings"][0]["code"], "FROZEN_ENTRY_OR_ORDER_DRIFT")

    def test_accepts_nonconstant_exit_and_preserved_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"><Param key="#Period#">14</Param></Item>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="ATR"><Param key="#Period#">21</Param></Item>')
            result = lint_sqx_semantics.lint(candidate, base)
            self.assertTrue(result["passed"])
            self.assertTrue(result["frozen_contract"]["entry_and_orders_preserved"])


if __name__ == "__main__":
    unittest.main()
