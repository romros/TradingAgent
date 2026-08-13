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
            "detection_latency_seconds": 600,
            "observed_quote": {"market_open": True, "bid": price_bid, "ask": price_ask,
                               "open_fee_bps": 2, "close_fee_bps": 0}}


class PaperFollowTest(unittest.TestCase):
    def test_long_uses_observed_ask_then_bid_and_costs(self):
        rows = [event("Open", 99, 100, "2026-08-13T10:00:00Z"),
                event("Close", 102, 103, "2026-08-13T11:00:00Z")]
        result = paper.replay(rows)
        trade = result["closed"][0]
        self.assertAlmostEqual(trade["paper_notional_usdc"], 250)
        self.assertAlmostEqual(trade["gross_pnl_usdc"], 5)
        self.assertAlmostEqual(trade["copy_net_pnl_usdc"], 4.95)
        self.assertFalse(result["live_trading_authorized"])

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
