import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import reality_transfer


def base_case():
    return {
        "candidate_id": "demo", "instrument": "GENERIC", "venue": "venue",
        "generation_period": {"start": "2004", "end": "2015"},
        "sealed_period": {"start": "2024", "end": "2026", "used_in_development": False},
        "mechanism": {"hypothesis": "persistent mechanism", "falsifier": "negative comparable regime"},
        "normalization": {"price_distances": "atr", "position_risk": "equity_percent"},
        "regime_results": [
            {"id": "2008", "tags": ["crisis"], "trades": 30, "net_expectancy": .1, "comparable_to_current": True},
            {"id": "2013", "tags": ["bear"], "trades": 30, "net_expectancy": .05, "comparable_to_current": False},
        ],
        "current_execution": {"price_asof": "2026-08-01", "spread": 1, "slippage": 1, "commission": 1, "minimum_position_notional": 100, "account_equity": 200, "liquidation_checked": True, "net_expectancy": .02},
    }


class RealityTransferTest(unittest.TestCase):
    def test_passes_diverse_comparable_and_executable(self):
        result = reality_transfer.assess(base_case())
        self.assertEqual(result["decision"], "OBRIR HOLDOUT")
        self.assertEqual(result["economics"]["required_leverage"], .5)

    def test_rejects_cost_failure(self):
        case = base_case(); case["current_execution"]["net_expectancy"] = -.01
        self.assertEqual(reality_transfer.assess(case)["decision"], "DESCARTAR")

    def test_rejects_old_bull_dependency(self):
        case = base_case(); case["regime_results"] = [{"id": "2004-2011", "tags": ["secular_bull"], "trades": 50, "net_expectancy": .2, "comparable_to_current": False}]
        self.assertEqual(reality_transfer.assess(case)["decision"], "DESCARTAR")

    def test_missing_data_fails_closed(self):
        self.assertEqual(reality_transfer.assess({"candidate_id": "x"})["decision"], "INCOMPLET")

    def test_placeholders_are_incomplete_not_a_failed_edge(self):
        case = base_case()
        case["current_execution"]["evidence_complete"] = False
        case["current_execution"]["net_expectancy"] = 0
        result = reality_transfer.assess(case)
        self.assertEqual(result["decision"], "INCOMPLET")
        self.assertEqual(result["main_risk"], "economia actual no verificada")

    def test_rejects_minimum_size_above_safe_leverage(self):
        case = base_case()
        case["current_execution"].update({"minimum_position_notional": 2000, "max_safe_leverage": 5})
        self.assertEqual(reality_transfer.assess(case)["decision"], "DESCARTAR")

    def test_does_not_assume_safe_leverage(self):
        case = base_case()
        case["current_execution"]["minimum_position_notional"] = 400
        self.assertEqual(reality_transfer.assess(case)["decision"], "PROVA DIRIGIDA")

    def test_sealed_pass_moves_only_to_paper_trading(self):
        case = base_case()
        case["sealed_period"].update({"executed": True, "passed": True})
        result = reality_transfer.assess(case)
        self.assertEqual(result["decision"], "PREPARAR PAPER TRADING")
        self.assertIn("no autorització", result["limits"])

    def test_calculates_small_account_economics_without_inventing_edge(self):
        case = base_case()
        case["current_execution"].update({
            "risk_per_trade_pct": 1,
            "net_expectancy_per_trade_account": .08,
            "expected_trades_per_year": 40,
        })
        economics = reality_transfer.assess(case)["economics"]
        self.assertEqual(economics["risk_per_trade_amount"], 2)
        self.assertEqual(economics["estimated_net_per_year"], 3.2)
        self.assertEqual(economics["estimated_net_per_year_pct"], 1.6)


if __name__ == "__main__":
    unittest.main()
