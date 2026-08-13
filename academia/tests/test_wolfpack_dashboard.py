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


if __name__ == "__main__":
    unittest.main()
