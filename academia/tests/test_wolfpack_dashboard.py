import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parents[1] / "projects" / "wolfpack" / "dashboard.py"
spec = importlib.util.spec_from_file_location("dashboard", MODULE)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTest(unittest.TestCase):
    def test_state_separates_real_and_simulated_messages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 8, 13, 15, tzinfo=timezone.utc)
            event = {"detected_at": "2026-08-13T14:55:00Z", "wallet_sha256": "abcdef1234",
                     "position_sha256": "p", "pair": "BTC/USD", "action": "Open", "side": "B",
                     "execution_price": 64000, "detection_latency_seconds": 400}
            (root / "follows").write_text(json.dumps(event) + "\n")
            (root / "heartbeat").write_text(json.dumps({"checked_at": "2026-08-13T14:59:00Z"}))
            (root / "paper").write_text(json.dumps({"starting_equity_usdc": 500,
                                                    "ending_equity_usdc": 501,
                                                    "open_positions": [{}], "closed": [], "skipped": []}))
            state = dashboard.build_state(root / "follows", root / "heartbeat",
                                          root / "paper", root / "checkpoint", now)
            self.assertEqual(state["health"]["follower"], "healthy")
            self.assertFalse(state["messages"][0]["simulated"])
            self.assertTrue(all(row["simulated"] for row in state["simulations"]))
            self.assertFalse(state["paper"]["live_trading_authorized"])
            self.assertEqual(state["assets"][0]["asset"], "BTC/USD")
            self.assertEqual(state["assets"][0]["open_source"], 1)
            self.assertEqual(state["tracking"][0]["source_status"], "OPEN")
            self.assertEqual(state["tracking"][0]["paper_status"], "NOT_COPIED")
            self.assertEqual(state["global_signal"]["decision"], "NO_SIGNAL")
            self.assertFalse(state["global_signal"]["live_trading_authorized"])
            self.assertEqual(state["link_watch"], {})
            self.assertEqual(state["opportunity_monitor"]["market"]["situation"], "PARTIAL_OR_STALE")

    def test_market_overview_and_paper_csv_are_factual(self):
        now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
        rows = [
            {"captured_at": "2026-08-14T11:00:00Z", "sources": {"ostium": [
                {"instrument": "BTC/USD", "mid": 100, "spread_bps": 2, "market_open": True}]}},
            {"captured_at": "2026-08-14T12:00:00Z", "sources": {"ostium": [
                {"instrument": "BTC/USD", "mid": 101, "spread_bps": 3, "market_open": True}]}}
        ]
        overview = dashboard.market_overview(rows, now)
        btc = overview["universe"][0]
        self.assertEqual(btc["status"], "LIVE")
        self.assertAlmostEqual(btc["change_1h_pct"], 1.0)
        exported = dashboard.paper_csv({"open_positions": [{"position_sha256": "p", "pair": "BTC/USD"}]})
        self.assertIn(b"paper_status", exported)
        self.assertIn(b"OPEN,p", exported)

    def test_closed_source_and_paper_results_stay_separate(self):
        events = [{"position_sha256": "p", "wallet_sha256": "w", "pair": "BTC/USD",
                   "action": "Open", "side": "B", "notional_usd": 100,
                   "executed_at": "2026-08-13T10:00:00Z"},
                  {"position_sha256": "p", "wallet_sha256": "w", "pair": "BTC/USD",
                   "action": "Close", "side": "B", "notional_usd": 100,
                   "closed_pnl_usd": 8, "executed_at": "2026-08-13T11:00:00Z"}]
        paper = {"closed": [{"position_sha256": "p", "copy_net_pnl_usdc": -1}]}
        assets, tracking = dashboard.tracking_views(events, paper)
        self.assertEqual(tracking[0]["source_status"], "CLOSED")
        self.assertEqual(tracking[0]["source_pnl_usd"], 8)
        self.assertEqual(tracking[0]["paper_net_pnl_usdc"], -1)
        self.assertEqual(assets[0]["paper_net_pnl_usdc"], -1)

    def test_roster_profiles_all_pack_members_and_blocks_portfolio(self):
        pack = {"members": [{"id": "wolf", "specialties": ["btc"],
                             "risk_flags": ["young_sample"]}]}
        events = [{"wallet_sha256": "wolf", "pair": "BTC/USD",
                   "detection_latency_seconds": 45}]
        paper = {"closed": [], "execution_realism_pass": False}
        roster = dashboard.roster_view(events, paper, pack)
        self.assertEqual(roster["profiles"][0]["status"], "OBSERVED")
        self.assertEqual(roster["profiles"][0]["confidence"], "NO_CLOSED_SAMPLE")
        self.assertEqual(roster["profiles"][0]["candidate_progress"], "0/10")
        self.assertEqual(roster["profiles"][0]["median_latency_seconds"], 45)
        self.assertFalse(roster["portfolio_gate"]["pass"])
        self.assertFalse(roster["portfolio_gate"]["live_trading_authorized"])


if __name__ == "__main__":
    unittest.main()
