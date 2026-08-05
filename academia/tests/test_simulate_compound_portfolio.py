import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import simulate_compound_portfolio


def trade(asset, entry, exit_, return_on_notional=.02, risk_pct=1, stop=2, leverage=2):
    return {"asset": asset, "entry_time": entry, "exit_time": exit_, "return_on_notional": return_on_notional, "risk_pct": risk_pct, "stop_distance_pct": stop, "leverage": leverage, "pair_max_leverage": 50, "opening_fee_bps": 3, "oracle_fee": .1, "rollover_bps": 0}


def case(trades):
    return {"initial_equity": 500, "maximum_effective_leverage": 5, "maximum_simultaneous_risk_pct": 4, "oracle_fee": .1, "trades": trades}


class CompoundPortfolioTest(unittest.TestCase):
    def test_compounds_from_realized_equity(self):
        result = simulate_compound_portfolio.simulate(case([
            trade("A", "2026-01-01", "2026-01-02"),
            trade("A", "2026-01-03", "2026-01-04"),
        ]))
        entries = [item for item in result["ledger"] if item["event"] == "entry"]
        self.assertGreater(entries[1]["notional"], entries[0]["notional"])
        self.assertGreater(result["final_equity"], 500)

    def test_leverage_changes_margin_not_risk_notional(self):
        low = simulate_compound_portfolio.simulate(case([trade("A", "1", "2", leverage=2)]))
        high = simulate_compound_portfolio.simulate(case([trade("A", "1", "2", leverage=4)]))
        low_entry = low["ledger"][0]
        high_entry = high["ledger"][0]
        self.assertEqual(low_entry["notional"], high_entry["notional"])
        self.assertGreater(low_entry["collateral"], high_entry["collateral"])

    def test_rejects_coincident_positions_over_aggregate_risk(self):
        result = simulate_compound_portfolio.simulate(case([
            trade("A", "1", "3", risk_pct=3),
            trade("B", "1", "3", risk_pct=3),
        ]))
        self.assertEqual(result["accepted_trades"], 1)
        self.assertEqual(result["skipped_trades"], 1)
        self.assertIn("simultaneous_risk_cap", result["ledger"][1]["reasons"])

    def test_fixed_oracle_cost_hurts_small_frequent_trades(self):
        trades = [trade("A", str(i * 2), str(i * 2 + 1), return_on_notional=0, risk_pct=.5) for i in range(10)]
        result = simulate_compound_portfolio.simulate(case(trades))
        self.assertLess(result["final_equity"], 500)


if __name__ == "__main__":
    unittest.main()
