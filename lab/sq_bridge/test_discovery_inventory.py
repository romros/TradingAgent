import tempfile
import unittest
import zipfile
from pathlib import Path

from discovery_inventory import inspect_sqx, inventory


STRATEGY = """<Strategy><Rule type='Signal'><signals><signal variable='L'>
<Item key='AND'><Block><Item key='IsRising'><Block><Item key='EMA' categoryType='indicator'>
<Param key='#Period#'>14</Param></Item></Block></Item></Block></Item>
</signal></signals></Rule></Strategy>"""


def make_sqx(path: Path, name: str, trades: int, profit: float, drawdown: float,
             fitness: float, complexity: int, period: int = 14) -> None:
    strategy = STRATEGY.replace(">14<", f">{period}<")
    settings = f"""<Results><Complexity>{complexity}</Complexity>
<Fingerprint strategyName='{name}' exact='1' trades='{trades}' profit='{profit}'
drawdown='{drawdown}' fitness='{fitness}' tradesHash='2'/></Results>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("settings.xml", settings)
        archive.writestr("strategy_Portfolio.xml", strategy)
        archive.writestr("version.txt", "5")


class DiscoveryInventoryTest(unittest.TestCase):
    def test_family_ignores_parameter_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_sqx(root / "a.sqx", "A", 100, 10, 2, .8, 5, 14)
            make_sqx(root / "b.sqx", "B", 90, 9, 3, .7, 6, 40)
            result = inventory(root)
            self.assertEqual(result["candidate_count"], 2)
            self.assertEqual(result["family_count"], 1)
            self.assertEqual(result["families"][0]["members"], ["A", "B"])
            self.assertEqual(result["archetype_count"], 1)
            self.assertEqual(result["archetypes"][0]["members"], ["A", "B"])

    def test_pareto_marks_dominated_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_sqx(root / "a.sqx", "A", 100, 10, 2, .8, 5)
            make_sqx(root / "b.sqx", "B", 90, 9, 3, .7, 6)
            result = inventory(root)
            self.assertEqual(result["pareto_candidates"], ["A"])
            self.assertTrue(result["pareto_is_descriptive_only"])

    def test_missing_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.sqx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("settings.xml", "<x/>")
            with self.assertRaisesRegex(ValueError, "membres absents"):
                inspect_sqx(path)


if __name__ == "__main__":
    unittest.main()
