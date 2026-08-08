import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import cost_gate_orders as gate


HEADER = '"Open time";"Open price";"Size";"Close time";"Profit/Loss";"MAE ($)"\n'


class CostGateOrdersTest(unittest.TestCase):
    def _csv(self, rows: list[str]) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False)
        tmp.write(HEADER + "\n".join(rows) + "\n")
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_fixed_cost_can_reject_small_gross_wins(self):
        path = self._csv([
            '"2020.01.01 00:00:00";"1.0";"0.1";"2020.01.02 00:00:00";"1.0";"-100"',
            '"2020.01.03 00:00:00";"1.0";"0.1";"2020.01.04 00:00:00";"1.0";"-100"',
        ])
        result = gate.evaluate(path)
        self.assertEqual(result["verdict"], "CHEAP_COST_FAIL")
        self.assertLess(result["scenarios"][0]["metrics"]["net_expectancy_usdc"], 0)

    def test_strong_edge_passes_base_and_respects_five_x_cap(self):
        path = self._csv([
            '"2020.01.01 00:00:00";"1.0";"0.1";"2020.01.02 00:00:00";"500";"-100"',
            '"2020.01.03 00:00:00";"1.0";"0.1";"2020.01.04 00:00:00";"-50";"-100"',
        ])
        result = gate.evaluate(path)
        self.assertTrue(result["passed_base"])
        self.assertLessEqual(result["sizing"]["selected_notional_usdc"], 2500)


if __name__ == "__main__":
    unittest.main()
