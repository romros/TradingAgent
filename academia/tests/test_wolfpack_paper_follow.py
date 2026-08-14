import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "projects" / "wolfpack" / "paper_follow.py"
spec = importlib.util.spec_from_file_location("paper_follow", MODULE)
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def event(action, price_bid, price_ask, detected, notional=1000, position="p"):
    return {"position_sha256": position, "wallet_sha256": "w", "pair": "BTC/USD",
            "action": action, "side": "B", "notional_usd": notional,
            "collateral_usd": 100, "detected_at": detected,
            "executed_at": detected, "execution_price": 100 if action == "Open" else 101,
            "detection_latency_seconds": 600,
            "observed_quote": {"market_open": True, "bid": price_bid, "ask": price_ask,
                               "mid": (price_bid + price_ask) / 2,
                               "open_fee_bps": 2, "close_fee_bps": 0,
                               "rollover_rate": {"long": "-0.01", "short": "0.005"},
                               "min_notional_usd": 5, "max_leverage": 75}}


class PaperFollowTest(unittest.TestCase):
    def test_long_uses_observed_ask_then_bid_and_costs(self):
        rows = [event("Open", 99, 100, "2026-08-13T10:00:00Z"),
                event("Close", 102, 103, "2026-08-13T11:00:00Z")]
        result = paper.replay(rows)
        trade = result["closed"][0]
        self.assertAlmostEqual(trade["paper_notional_usdc"], 250)
        self.assertAlmostEqual(trade["gross_pnl_usdc"], 5)
        self.assertIsNone(trade["copy_net_pnl_usdc"])
        self.assertAlmostEqual(trade["gross_pnl_usdc"], 5)
        self.assertFalse(result["live_trading_authorized"])
        self.assertFalse(result["execution_realism_pass"])
        self.assertTrue(result["execution_realism_blockers"])
        self.assertEqual(result["open_positions"], [])
        self.assertAlmostEqual(trade["source_gross_return_pct"], 1.0)
        self.assertAlmostEqual(trade["copy_gross_return_pct"], 2.0)
        self.assertAlmostEqual(trade["implementation_shortfall_bps"], -100.0)
        self.assertEqual(trade["entry_detection_latency_seconds"], 600)

    def test_missing_observed_quote_is_skipped(self):
        row = event("Open", 99, 100, "2026-08-13T10:00:00Z")
        row["observed_quote"] = None
        result = paper.replay([row])
        self.assertEqual(result["skipped"][0]["reason"], "missing_observable_bid_ask")

    def test_cross_day_trade_has_no_net_claim_until_rollover_is_known(self):
        rows = [event("Open", 99, 100, "2026-08-13T23:00:00Z"),
                event("Close", 102, 103, "2026-08-14T01:00:00Z")]
        trade = paper.replay(rows)["closed"][0]
        self.assertIsNone(trade["copy_net_pnl_usdc"])
        self.assertFalse(trade["cost_complete"])

    def test_open_position_keeps_identity_and_source_execution(self):
        result = paper.replay([event("Open", 99, 100, "2026-08-13T10:00:00Z")])
        position = result["open_positions"][0]
        self.assertEqual(position["position_sha256"], "p")
        self.assertEqual(position["source_entry_price"], 100)

    def test_sdk_size_slippage_takes_precedence_over_bid_ask(self):
        row = event("Open", 99, 101, "2026-08-13T10:00:00Z")
        row["observed_quote"].update({
            "mid": 100,
            "simulated_slippage_250": {
                "long": [{"ntl": "250", "slippage": "0.10"}],
                "short": [{"ntl": "250", "slippage": "0.20"}],
            },
        })
        position = paper.replay([row])["open_positions"][0]
        self.assertAlmostEqual(position["entry_price"], 100.1)
        self.assertEqual(position["slippage_model"], "sdk_simulated_250")

    def test_complete_cross_day_trade_charges_conservative_carry_and_can_pass_realism(self):
        opened = event("Open", 99, 100, "2026-08-13T10:00:00Z")
        closed = event("Close", 102, 103, "2026-08-14T10:00:00Z")
        for row in (opened, closed):
            row["observed_quote"]["simulated_slippage_250"] = {
                "long": [{"ntl": "250", "slippage": "0.01"}],
                "short": [{"ntl": "250", "slippage": "0.01"}],
            }
        result = paper.replay([opened, closed])
        trade = result["closed"][0]
        self.assertTrue(trade["cost_complete"])
        self.assertGreater(trade["carry_cost_usdc"], 0)
        self.assertIsNotNone(trade["liquidation_price_initial"])
        self.assertTrue(result["execution_realism_pass"])
        self.assertEqual(result["execution_realism_eligible_closed"], 1)

    def test_legacy_incomplete_close_is_excluded_not_mixed_with_new_realism_cohort(self):
        legacy = [event("Open", 99, 100, "2026-08-13T10:00:00Z"),
                  event("Close", 102, 103, "2026-08-13T11:00:00Z")]
        complete = [event("Open", 99, 100, "2026-08-14T10:00:00Z", position="new"),
                    event("Close", 102, 103, "2026-08-14T11:00:00Z", position="new")]
        for row in complete:
            row["observed_quote"]["simulated_slippage_250"] = {
                "long": [{"ntl": "250", "slippage": "0.01"}],
                "short": [{"ntl": "250", "slippage": "0.01"}],
            }
        result = paper.replay(legacy + complete)
        self.assertTrue(result["execution_realism_pass"])
        self.assertEqual(result["execution_realism_eligible_closed"], 1)
        self.assertEqual(result["execution_realism_excluded_closed"], 1)
