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

