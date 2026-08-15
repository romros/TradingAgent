import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "projects" / "wolfpack" / "paper_ledger.py"
spec = importlib.util.spec_from_file_location("paper_ledger", MODULE)
ledger = importlib.util.module_from_spec(spec); spec.loader.exec_module(ledger)


class PaperLedgerTest(unittest.TestCase):
    def test_merges_once_and_preserves_incomplete_cost_warning(self):
        wolf = {"starting_equity_usdc": 500, "ending_equity_usdc": 497,
                "closed": [{"position_sha256": "p", "copy_net_pnl_usdc": -3,
                            "cost_complete": True}], "open_positions": []}
        setup = {"experiment_id": "link", "status": "CLOSED_TARGET_COMPLETE",
                 "copy_net_pnl_usdc": 3.5, "cost_complete": False}
        result = ledger.build(wolf, [setup, setup])
        self.assertEqual(result["closed_count"], 2)
        self.assertAlmostEqual(result["ending_equity_usdc"], 500.5)
        self.assertFalse(result["cost_complete"])
        self.assertFalse(result["live_trading_authorized"])

    def test_active_standalone_is_open_and_later_close_deduplicates_it(self):
        active = {"experiment_id": "v40", "status": "PAPER_OPEN", "realized_pnl_usdc": -0.15,
                  "last_quote": {"mid": 9.4}, "position": {"direction": "SHORT",
                  "opened_at": "2026-08-15T06:00:00Z", "entry": 9.39,
                  "stop": 9.46, "target_1": 9.21, "target_2": 9.05,
                  "open_fee_remaining_usdc": 0.15}}
        result = ledger.build({"starting_equity_usdc": 500, "ending_equity_usdc": 500}, [], [active])
        self.assertEqual(result["open_count"], 1)
        self.assertEqual(result["trades"][0]["experiment_id"], "v40")
        self.assertEqual(result["trades"][0]["status"], "OPEN")
        closed = {"experiment_id": "v40", "status": "CLOSED_TARGET_COMPLETE",
                  "copy_net_pnl_usdc": 3, "cost_complete": True}
        deduplicated = ledger.build({"starting_equity_usdc": 500, "ending_equity_usdc": 500},
                                    [closed], [active])
        self.assertEqual(deduplicated["open_count"], 0)
        self.assertEqual(deduplicated["closed_count"], 1)
