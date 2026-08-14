import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "projects" / "wolfpack"))
import portfolio_signal as subject


def review(direction="LONG", decision="ENTER_PAPER", confidence=.9):
    return {"decision": decision, "confidence": confidence, "direction": direction,
            "entry": 100, "invalidation": 99, "target": 103, "expiry": "soon",
            "expected_net_gain_usdc": 5, "maximum_loss_usdc": 3}


class PortfolioSignalTest(unittest.TestCase):
    def test_one_reject_vetoes_council(self):
        result = subject.aggregate_council([review(), review(), review(decision="REJECT")])
        self.assertEqual(result["decision"], "REJECT")

    def test_aggressive_risk_ladder_sizes_from_stop(self):
        result = subject.size_position(equity_usdc=500, confidence=.9, entry=100,
                                       invalidation=99, stress_cost_bps=10,
                                       venue_max_leverage=100,
                                       safe_liquidation_leverage=8)
        self.assertEqual(result["risk_pct"], 3)
        self.assertLessEqual(result["leverage"], 5)
        self.assertLessEqual(result["maximum_loss_usdc"], 15)
        self.assertFalse(result["live_trading_authorized"])

    def test_two_titulars_and_unanimous_council_can_only_enter_paper(self):
        votes = [{"status": "TITULAR", "direction": "LONG", "evidence_weight": 1,
                  "expected_net_return": .04} for _ in range(2)]
        execution = {"entry": 100, "invalidation": 99, "target": 103, "expiry": "soon",
                     "stress_cost_bps": 10, "venue_max_leverage": 100,
                     "safe_liquidation_leverage": 8}
        result = subject.global_signal(titular_votes=votes,
                                       council_reviews=[review(), review(), review()],
                                       execution=execution)
        self.assertEqual(result["decision"], "ENTER_PAPER")
        self.assertGreaterEqual(result["reward_risk"], 1.5)
        self.assertFalse(result["live_trading_authorized"])

    def test_no_signal_without_two_titulars(self):
        result = subject.global_signal(titular_votes=[], council_reviews=[], execution={})
        self.assertEqual(result["decision"], "NO_SIGNAL")


if __name__ == "__main__":
    unittest.main()
