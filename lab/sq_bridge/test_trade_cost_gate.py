import csv
import json
import tempfile
import unittest
from pathlib import Path

from trade_cost_gate import _nearest_rank, evaluate, validate_contract_units


class TradeCostGateTest(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(_nearest_rank([4, 1, 3, 2], 0.75), 3)

    def test_costs_can_falsify_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Open price", "Size", "Profit/Loss", "MAE ($)", "Open time", "Close time"], delimiter=";")
                writer.writeheader()
                for pnl in (2, 2, -1, 2, -1):
                    writer.writerow({"Open price": 100, "Size": 1, "Profit/Loss": pnl, "MAE ($)": -2})
            methodology = {
                "small_account": {"canonical_capital_usdc": 200, "maximum_risk_per_trade_pct": 1,
                    "maximum_portfolio_margin_pct": 35, "minimum_net_expectancy_usdc": .1,
                    "minimum_net_profit_factor": 1.1, "leverage_grid": [1, 2, 5, 10]},
                "robustness": {"monte_carlo_runs": 100, "minimum_profitable_monte_carlo_ratio": .7},
            }
            scenarios = [{"name": "base", "roundtrip_bps": 1},
                         {"name": "stress", "roundtrip_bps": 500}]
            result = evaluate(path, methodology, scenarios, broker_max_leverage=10, venue_max_leverage=100)
            self.assertEqual(result["sizing"]["selected_notional_usdc"], 100)
            self.assertTrue(result["scenarios"][0]["passed"])
            self.assertFalse(result["scenarios"][1]["passed"])
            self.assertEqual(result["verdict"], "BASE_ONLY_NOT_ROBUST")


    def test_source_equity_preserves_variable_risk_sizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Open price", "Size", "Profit/Loss", "MAE ($)", "Open time", "Close time"], delimiter=";")
                writer.writeheader()
                writer.writerow({"Open price": 100, "Size": 10, "Profit/Loss": 100, "MAE ($)": -10})
                writer.writerow({"Open price": 100, "Size": 5, "Profit/Loss": -25, "MAE ($)": -5})
            methodology = {
                "small_account": {"canonical_capital_usdc": 200, "maximum_risk_per_trade_pct": 1,
                    "maximum_portfolio_margin_pct": 35, "minimum_net_expectancy_usdc": -10,
                    "minimum_net_profit_factor": 0, "leverage_grid": [1, 2, 5, 10]},
                "robustness": {"monte_carlo_runs": 10, "minimum_profitable_monte_carlo_ratio": 0},
            }
            result = evaluate(path, methodology, [{"name": "base", "roundtrip_bps": 10, "fixed_cost_usdc": .1}],
                              broker_max_leverage=10, venue_max_leverage=10, source_equity=10000)
            self.assertEqual(result["sizing"]["sizing_mode"], "PRESERVE_SQ_RISK_SIZING")
            self.assertEqual(result["sizing"]["order_scale"], .02)
            self.assertEqual(result["sizing"]["selected_notional_usdc"], 20)
            self.assertAlmostEqual(result["scenarios"][0]["metrics"]["net_pnl_usdc"], 1.27)

    def test_source_equity_cannot_bypass_mae_risk_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["Open price", "Size", "Profit/Loss", "MAE ($)", "Open time", "Close time"], delimiter=";")
                writer.writeheader()
                writer.writerow({"Open price": 100, "Size": 100, "Profit/Loss": 100, "MAE ($)": -1000})
            methodology = {
                "small_account": {"canonical_capital_usdc": 200, "maximum_risk_per_trade_pct": 1,
                    "maximum_portfolio_margin_pct": 35, "minimum_net_expectancy_usdc": -10,
                    "minimum_net_profit_factor": 0, "leverage_grid": [1, 2, 5, 10]},
                "robustness": {"monte_carlo_runs": 10, "minimum_profitable_monte_carlo_ratio": 0},
            }
            result = evaluate(path, methodology, [{"name": "base", "roundtrip_bps": 0}],
                              broker_max_leverage=10, venue_max_leverage=10, source_equity=10000)
            self.assertAlmostEqual(result["sizing"]["risk_notional_usdc"], 20)
            self.assertAlmostEqual(result["sizing"]["selected_notional_usdc"], 20)

    def test_duration_dependent_rollover_is_charged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            with path.open("w", newline="") as handle:
                fields = ["Open price", "Size", "Profit/Loss", "MAE ($)", "Open time", "Close time"]
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
                writer.writeheader()
                writer.writerow({"Open price": 100, "Size": 1, "Profit/Loss": 10, "MAE ($)": -2,
                                 "Open time": "2025.01.01 00:00:00", "Close time": "2026.01.01 06:00:00"})
            methodology = {
                "small_account": {"canonical_capital_usdc": 200, "maximum_risk_per_trade_pct": 1,
                    "maximum_portfolio_margin_pct": 100, "minimum_net_expectancy_usdc": -100,
                    "minimum_net_profit_factor": 0, "leverage_grid": [1]},
                "robustness": {"monte_carlo_runs": 10, "minimum_profitable_monte_carlo_ratio": 0},
            }
            result = evaluate(path, methodology,
                              [{"name": "carry", "roundtrip_bps": 0, "annual_rollover_pct": 10}],
                              broker_max_leverage=1, venue_max_leverage=1)
            self.assertAlmostEqual(result["scenarios"][0]["metrics"]["net_pnl_usdc"], 0, places=6)

    def test_eurusd_requires_explicit_lot_multiplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orders.csv"
            path.write_text('"Symbol";"Size"\n"EURUSD_M1_dukas";"0.1"\n')
            with self.assertRaisesRegex(ValueError, "100000"):
                validate_contract_units(path, 1)

if __name__ == "__main__":
    unittest.main()
