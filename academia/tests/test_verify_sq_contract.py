import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_sq_contract


class SqContractTest(unittest.TestCase):
    def _fixtures(self, root: Path, strategy: str = "EnterAtStop Highest Lowest"):
        project = root / "project.cfx"
        artifact = root / "candidate.sqx"
        config = """<Project><CrossChecks>
          <Check name="MonteCarloParameters" use="true"/>
          <Check name="MonteCarloManipulation" use="false"/>
          </CrossChecks><Slippage value="800"/></Project>"""
        with zipfile.ZipFile(project, "w") as archive:
            archive.writestr("config.xml", config)
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("strategy_Portfolio.xml", strategy)
        return project, artifact

    def test_passes_exact_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            project, artifact = self._fixtures(Path(directory))
            result = verify_sq_contract.verify(
                project, [artifact], ["EnterAtStop", "Highest", "Lowest"],
                ["MonteCarloParameters"], {"Slippage": "800"},
            )
            self.assertTrue(result["passed"])
            self.assertEqual(result["artifacts_checked"], 1)

    def test_rejects_inherited_crosscheck_and_missing_mechanism(self):
        with tempfile.TemporaryDirectory() as directory:
            project, artifact = self._fixtures(Path(directory), "EnterAtMarket EMA")
            result = verify_sq_contract.verify(
                project, [artifact], ["EnterAtStop", "Highest", "Lowest"],
                None, {},
            )
            self.assertFalse(result["passed"])
            self.assertIn("EnterAtStop", result["artifact_results"][0]["missing_tokens"])

            # Una llista esperada activa el control exacte i detecta herència.
            result = verify_sq_contract.verify(
                project, [artifact], [], ["MonteCarloManipulation"], {},
            )
            self.assertFalse(result["passed"])
            self.assertIn("MonteCarloParameters", result["active_crosschecks"])

    def test_rejects_crosscheck_when_none_are_expected(self):
        with tempfile.TemporaryDirectory() as directory:
            project, artifact = self._fixtures(Path(directory))
            result = verify_sq_contract.verify(project, [artifact], [], [], {})
            self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
