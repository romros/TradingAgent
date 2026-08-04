import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lint_sqx_semantics


def _sqx(path: Path, exit_expression: str, direction: str = "1", entry_key: str = "SMA", entry_period: str = "20") -> Path:
    strategy = f"""<Root><Strategy engine="MetaTrader4"><Events><Event key="OnBarUpdate">
      <Rule name="Trading signals"><signals>
        <signal variable="entry-long"><Item key="{entry_key}"><Param key="#Period#">{entry_period}</Param></Item></signal>
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

    def test_allows_entry_change_but_keeps_orders_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"/>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="ATR"/>', entry_key="EMA", entry_period="30")
            result = lint_sqx_semantics.lint(candidate, base, allow_entry_change=True)
            self.assertTrue(result["passed"])
            self.assertFalse(result["frozen_contract"]["entry_preserved"])
            self.assertTrue(result["frozen_contract"]["orders_preserved"])

    def test_allows_only_slpt_parameter_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"/>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="ATR"/>')
            for path, value in ((base, "2.0"), (candidate, "3.5")):
                with zipfile.ZipFile(path, "r") as archive:
                    strategy = archive.read("strategy_Portfolio.xml").decode().replace(
                        '<Param key="#Size#"><Formula key="SQ.Formulas.Size.UseGlobalMM"/></Param>',
                        f'<Param key="#Size#"><Formula key="SQ.Formulas.Size.UseGlobalMM"/></Param><Param key="#StopLoss.StopLoss#">{value}</Param>',
                    )
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("strategy_Portfolio.xml", strategy)
            rejected = lint_sqx_semantics.lint(candidate, base)
            accepted = lint_sqx_semantics.lint(candidate, base, allow_slpt_change=True)
            self.assertFalse(rejected["passed"])
            self.assertTrue(accepted["passed"])
            self.assertTrue(accepted["frozen_contract"]["entry_preserved"])
            self.assertTrue(accepted["frozen_contract"]["orders_preserved"])
            self.assertTrue(accepted["frozen_contract"]["exit_signals_preserved"])
            self.assertTrue(accepted["frozen_contract"]["slpt_changed"])

    def test_rejects_slpt_claim_without_a_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = _sqx(root / "base.sqx", '<Item key="ATR"/>')
            candidate = _sqx(root / "candidate.sqx", '<Item key="ATR"/>')
            result = lint_sqx_semantics.lint(candidate, base, allow_slpt_change=True)
            self.assertFalse(result["passed"])
            self.assertEqual(result["findings"][0]["code"], "EXPECTED_SLPT_CHANGE_MISSING")


if __name__ == "__main__":
    unittest.main()
