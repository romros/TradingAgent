import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import evaluate_vix_managed_spy as subject


class EvaluateVixManagedSpyTest(unittest.TestCase):
    def test_prior_vix_and_first_session_only(self):
        prices = [
            {"date": "2020-01-03", "adjusted_open": 100},
            {"date": "2020-01-06", "adjusted_open": 102},
            {"date": "2020-01-07", "adjusted_open": 999},
            {"date": "2020-01-13", "adjusted_open": 104},
        ]
        periods = subject.build_weekly_periods(
            prices, {"2020-01-02": 40, "2020-01-03": 10, "2020-01-06": 5}
        )
        self.assertEqual([row["date"] for row in periods], ["2020-01-03", "2020-01-06"])
        self.assertEqual(periods[0]["exposure"], 0.5)
        self.assertEqual(periods[1]["exposure"], 1.0)
        self.assertAlmostEqual(periods[1]["return"], 104 / 102 - 1)

    def test_cli_refuses_to_reveal_before_cost_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            gate = Path(directory) / "gate.json"
            gate.write_text(json.dumps({"decision": "INSUFFICIENT_OPEN_SESSION_COVERAGE"}))
            old_argv = sys.argv
            sys.argv = ["tool", "--spy", "missing", "--vix", "missing", "--cost-gate", str(gate),
                        "--output", str(Path(directory) / "out.json")]
            try:
                with self.assertRaises(SystemExit) as error:
                    subject.main()
                self.assertIn("not frozen", str(error.exception))
            finally:
                sys.argv = old_argv

    def test_roundtrip_is_split_across_one_way_turnover_and_carry_is_charged(self):
        periods = [{"date": "2020-01-06", "return": 0.01, "exposure": 1.0}]
        result = subject._metrics(periods, True, 10.0, 5.21775)
        expected = 0.01 - 0.0005 - 0.001
        self.assertAlmostEqual(result["net_return_pct"], expected * 100)

    def test_development_gate_is_literal_and_not_score_based(self):
        result = {
            "managed": {"net_return_pct": 10, "maximum_drawdown_pct": 8,
                        "return_over_drawdown": 1.25, "positive_years": 6,
                        "year_count": 8},
            "always_long": {"maximum_drawdown_pct": 10,
                            "return_over_drawdown": 1.0},
        }
        self.assertTrue(subject.development_gate(result)["pass"])
        result["managed"]["positive_years"] = 5
        self.assertFalse(subject.development_gate(result)["pass"])

    def test_validation_gate_compares_with_development(self):
        result = {
            "managed": {"net_return_pct": 5, "maximum_drawdown_pct": 9,
                        "return_over_drawdown": 1.6, "positive_years": 3,
                        "year_count": 5},
            "always_long": {"maximum_drawdown_pct": 10},
        }
        development = {"managed": {"return_over_drawdown": 2.0}}
        self.assertTrue(subject.validation_gate(result, development)["pass"])


if __name__ == "__main__":
    unittest.main()
